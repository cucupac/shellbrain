"""Concept-context rendering for normal read packs."""

from __future__ import annotations

from typing import Any

from app.core.contracts.retrieval import MemoryReadRequest, ReadConceptsExpandRequest
from app.core.entities.concepts import (
    Concept,
    ConceptClaim,
    ConceptLifecycleStatus,
    ConceptMemoryLink,
)
from app.core.entities.memories import Memory
from app.core.ports.concept_repositories import IConceptsRepo
from app.core.ports.memory_repositories import IMemoriesRepo
from app.core.policies.concepts.search import rank_concept_search_rows


AVAILABLE_FACETS = ("claims", "relations", "groundings", "memory_links", "evidence")
MAX_KEY_CLAIMS = 3
MAX_ORIENTATION_CHARS = 600
MAX_EXPAND_HANDLES = 5


def append_concepts_to_pack(
    *,
    pack: dict[str, Any],
    request: MemoryReadRequest,
    concepts: IConceptsRepo,
    memories: IMemoriesRepo,
) -> dict[str, Any]:
    """Append the stable concept-context section to one read pack."""

    concept_expand = _concept_expand(request)
    if concept_expand.mode == "none":
        pack["concepts"] = {
            "mode": "none",
            "items": [],
            "missing_refs": [],
            "guidance": "Concept context suppressed by request.",
        }
        return pack

    if concept_expand.mode == "explicit":
        items, missing_refs = _explicit_concept_items(
            request=request,
            concept_expand=concept_expand,
            concepts=concepts,
            memories=memories,
        )
        pack["concepts"] = {
            "mode": "explicit",
            "items": items,
            "missing_refs": missing_refs,
            "guidance": _guidance_for_items(items),
        }
        return pack

    items = _auto_concept_items(
        pack=pack,
        request=request,
        concept_expand=concept_expand,
        concepts=concepts,
        memories=memories,
    )
    pack["concepts"] = {
        "mode": "auto",
        "items": items,
        "missing_refs": [],
        "guidance": _guidance_for_items(items),
    }
    return pack


def _concept_expand(request: MemoryReadRequest) -> ReadConceptsExpandRequest:
    """Resolve concept expansion controls from a validated read request."""

    if request.expand is None:
        return ReadConceptsExpandRequest()
    return request.expand.concepts


def _auto_concept_items(
    *,
    pack: dict[str, Any],
    request: MemoryReadRequest,
    concept_expand: ReadConceptsExpandRequest,
    concepts: IConceptsRepo,
    memories: IMemoriesRepo,
) -> list[dict[str, Any]]:
    memory_ids = _pack_memory_ids(pack)
    candidates: dict[str, dict[str, Any]] = {}

    for link_match in concepts.find_concepts_for_memory_ids(
        repo_id=request.repo_id, memory_ids=memory_ids
    ):
        concept_id = str(link_match["concept_id"])
        candidate = candidates.setdefault(concept_id, {"score": 0.0, "why": []})
        status = str(link_match.get("status") or "active")
        confidence = float(link_match.get("confidence") or 0.5)
        candidate["score"] += 10.0 * _status_multiplier(status) * max(confidence, 0.1)
        _append_linked_memory_reason(candidate["why"], link_match)

    for query_match in rank_concept_search_rows(
        concepts.list_concept_search_rows(repo_id=request.repo_id),
        query=request.query,
        limit=20,
    ):
        concept_id = str(query_match["concept_id"])
        candidate = candidates.setdefault(concept_id, {"score": 0.0, "why": []})
        candidate["score"] += float(query_match.get("score") or 1.0)
        _append_query_reason(candidate["why"], query_match)

    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for concept_id, candidate in candidates.items():
        bundle = concepts.get_concept_bundle(
            repo_id=request.repo_id, concept_ref=concept_id
        )
        if bundle is None:
            continue
        score = float(candidate["score"]) * _freshness_multiplier(bundle)
        ranked.append(
            (score, str(bundle["concept"].slug), {**candidate, "bundle": bundle})
        )
    ranked.sort(key=lambda item: (-item[0], item[1]))

    items: list[dict[str, Any]] = []
    for _, _, candidate in ranked[: concept_expand.max_auto]:
        items.append(
            _render_concept_item(
                bundle=candidate["bundle"],
                facets=(),
                why_matched=candidate["why"],
                query=request.query,
                concepts=concepts,
                memories=memories,
            )
        )
    return items


def _explicit_concept_items(
    *,
    request: MemoryReadRequest,
    concept_expand: ReadConceptsExpandRequest,
    concepts: IConceptsRepo,
    memories: IMemoriesRepo,
) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    missing_refs: list[str] = []
    for concept_ref in concept_expand.refs:
        bundle = concepts.get_concept_bundle(
            repo_id=request.repo_id, concept_ref=concept_ref
        )
        if bundle is None:
            missing_refs.append(concept_ref)
            continue
        items.append(
            _render_concept_item(
                bundle=bundle,
                facets=tuple(concept_expand.facets),
                why_matched=[{"reason": "explicit_ref", "ref": concept_ref}],
                query=request.query,
                concepts=concepts,
                memories=memories,
            )
        )
    return items, missing_refs


def _render_concept_item(
    *,
    bundle: dict[str, Any],
    facets: tuple[str, ...],
    why_matched: list[dict[str, Any]],
    query: str,
    concepts: IConceptsRepo,
    memories: IMemoriesRepo,
) -> dict[str, Any]:
    concept: Concept = bundle["concept"]
    claims: list[ConceptClaim] = list(bundle["claims"])
    item: dict[str, Any] = {
        "ref": concept.slug,
        "id": concept.id,
        "name": concept.name,
        "kind": concept.kind.value,
        "orientation": _orientation(concept, claims),
        "why_matched": why_matched,
        "freshness": _freshness(bundle),
        "key_claims": _key_claims(claims),
        "available_facets": list(AVAILABLE_FACETS),
        "expand": _expand_handles(concept=concept, query=query),
    }
    requested = set(facets)
    if "claims" in requested:
        item["claims"] = [_claim_payload(claim) for claim in _sort_claims(claims)]
    if "relations" in requested:
        item["relations"] = _relation_payloads(bundle, concepts)
    if "groundings" in requested:
        item["groundings"] = _grounding_payloads(bundle)
    if "memory_links" in requested:
        item["memory_links"] = _memory_link_payloads(bundle, memories)
    if "evidence" in requested:
        item["evidence"] = _evidence_payloads(bundle)
    return item


def _pack_memory_ids(pack: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for section_name in ("direct", "explicit_related", "implicit_related"):
        for item in pack.get(section_name, []):
            memory_id = str(item["memory_id"])
            if memory_id in seen:
                continue
            seen.add(memory_id)
            ids.append(memory_id)
    return ids


def _append_linked_memory_reason(
    reasons: list[dict[str, Any]], link_match: dict[str, Any]
) -> None:
    role = str(link_match.get("role") or "")
    existing = next(
        (
            item
            for item in reasons
            if item.get("reason") == "linked_memory" and item.get("role") == role
        ),
        None,
    )
    if existing is None:
        reasons.append({"reason": "linked_memory", "role": role, "count": 1})
    else:
        existing["count"] = int(existing["count"]) + 1


def _append_query_reason(
    reasons: list[dict[str, Any]], query_match: dict[str, Any]
) -> None:
    reason = str(query_match.get("reason") or "query_match")
    matched = str(query_match.get("matched") or "")
    if any(
        item.get("reason") == reason and item.get("matched") == matched
        for item in reasons
    ):
        return
    reasons.append({"reason": reason, "matched": matched})


def _status_multiplier(status: str) -> float:
    return {
        ConceptLifecycleStatus.ACTIVE.value: 1.0,
        ConceptLifecycleStatus.MAYBE_STALE.value: 0.65,
        ConceptLifecycleStatus.STALE.value: 0.25,
        ConceptLifecycleStatus.SUPERSEDED.value: 0.1,
        ConceptLifecycleStatus.WRONG.value: 0.0,
    }.get(status, 0.5)


def _freshness_multiplier(bundle: dict[str, Any]) -> float:
    freshness = _freshness(bundle)
    if freshness["status"] == "active":
        return 1.0
    if freshness["status"] == "maybe_stale":
        return 0.7
    return 0.35


def _freshness(bundle: dict[str, Any]) -> dict[str, Any]:
    statuses: list[str] = []
    for key in ("relations", "claims", "groundings", "memory_links"):
        for record in bundle[key]:
            statuses.append(record.lifecycle.status.value)
    maybe_stale = statuses.count(ConceptLifecycleStatus.MAYBE_STALE.value)
    stale = statuses.count(ConceptLifecycleStatus.STALE.value)
    wrong = statuses.count(ConceptLifecycleStatus.WRONG.value)
    superseded = statuses.count(ConceptLifecycleStatus.SUPERSEDED.value)
    status = "active"
    if wrong or stale:
        status = "stale"
    elif maybe_stale or superseded:
        status = "maybe_stale"
    return {
        "status": status,
        "active_records": statuses.count(ConceptLifecycleStatus.ACTIVE.value),
        "maybe_stale_records": maybe_stale,
        "stale_records": stale,
        "superseded_records": superseded,
        "wrong_records": wrong,
    }


def _orientation(concept: Concept, claims: list[ConceptClaim]) -> str:
    definition = next(
        (
            claim.text
            for claim in _sort_claims(claims)
            if claim.claim_type.value == "definition"
            and claim.lifecycle.status == ConceptLifecycleStatus.ACTIVE
        ),
        None,
    )
    text = definition or f"{concept.name} is a {concept.kind.value} concept."
    return _truncate(text, MAX_ORIENTATION_CHARS)


def _key_claims(claims: list[ConceptClaim]) -> list[dict[str, Any]]:
    active_claims = [
        claim
        for claim in _sort_claims(claims)
        if claim.lifecycle.status == ConceptLifecycleStatus.ACTIVE
    ]
    return [_claim_payload(claim) for claim in active_claims[:MAX_KEY_CLAIMS]]


def _sort_claims(claims: list[ConceptClaim]) -> list[ConceptClaim]:
    priority = {
        "definition": 0,
        "behavior": 1,
        "invariant": 2,
        "failure_mode": 3,
        "usage_note": 4,
        "open_question": 5,
    }
    return sorted(
        claims,
        key=lambda claim: (
            claim.lifecycle.status.value != ConceptLifecycleStatus.ACTIVE.value,
            priority.get(claim.claim_type.value, 99),
            claim.text,
        ),
    )


def _claim_payload(claim: ConceptClaim) -> dict[str, Any]:
    return {
        "id": claim.id,
        "type": claim.claim_type.value,
        "text": claim.text,
        "status": claim.lifecycle.status.value,
        "confidence": claim.lifecycle.confidence,
    }


def _relation_payloads(
    bundle: dict[str, Any], concepts: IConceptsRepo
) -> list[dict[str, Any]]:
    relations = list(bundle["relations"])
    endpoint_ids = []
    for relation in relations:
        endpoint_ids.extend([relation.subject_concept_id, relation.object_concept_id])
    endpoints = {
        concept.id: concept
        for concept in concepts.list_concepts_by_ids(
            repo_id=bundle["concept"].repo_id, concept_ids=endpoint_ids
        )
    }
    payloads: list[dict[str, Any]] = []
    for relation in sorted(
        relations,
        key=lambda item: (
            item.predicate.value,
            item.subject_concept_id,
            item.object_concept_id,
        ),
    ):
        payloads.append(
            {
                "id": relation.id,
                "predicate": relation.predicate.value,
                "subject": _concept_ref_payload(
                    endpoints.get(relation.subject_concept_id),
                    relation.subject_concept_id,
                ),
                "object": _concept_ref_payload(
                    endpoints.get(relation.object_concept_id),
                    relation.object_concept_id,
                ),
                "status": relation.lifecycle.status.value,
                "confidence": relation.lifecycle.confidence,
            }
        )
    return payloads


def _grounding_payloads(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    anchors_by_id = {anchor.id: anchor for anchor in bundle["anchors"]}
    payloads: list[dict[str, Any]] = []
    for grounding in sorted(
        bundle["groundings"], key=lambda item: (item.role.value, item.anchor_id)
    ):
        anchor = anchors_by_id.get(grounding.anchor_id)
        payloads.append(
            {
                "id": grounding.id,
                "role": grounding.role.value,
                "status": grounding.lifecycle.status.value,
                "confidence": grounding.lifecycle.confidence,
                "anchor": {
                    "id": anchor.id,
                    "kind": anchor.kind.value,
                    "locator": anchor.locator_json,
                    "status": anchor.status.value,
                }
                if anchor is not None
                else None,
            }
        )
    return payloads


def _memory_link_payloads(
    bundle: dict[str, Any], memories: IMemoriesRepo
) -> list[dict[str, Any]]:
    links: list[ConceptMemoryLink] = list(bundle["memory_links"])
    memory_by_id: dict[str, Memory] = {
        memory.id: memory
        for memory in memories.list_by_ids([link.memory_id for link in links])
    }
    payloads: list[dict[str, Any]] = []
    for link in sorted(links, key=lambda item: (item.role.value, item.memory_id)):
        memory = memory_by_id.get(link.memory_id)
        payloads.append(
            {
                "id": link.id,
                "role": link.role.value,
                "status": link.lifecycle.status.value,
                "confidence": link.lifecycle.confidence,
                "memory_id": link.memory_id,
                "kind": memory.kind.value if memory else None,
                "text": memory.text if memory else None,
            }
        )
    return payloads


def _evidence_payloads(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": evidence.id,
            "target_type": evidence.target_type.value,
            "target_id": evidence.target_id,
            "kind": evidence.evidence_kind.value,
            "anchor_id": evidence.anchor_id,
            "memory_id": evidence.memory_id,
            "commit_ref": evidence.commit_ref,
            "transcript_ref": evidence.transcript_ref,
            "note": evidence.note,
        }
        for evidence in sorted(
            bundle["evidence"],
            key=lambda item: (
                item.target_type.value,
                item.target_id,
                item.evidence_kind.value,
                item.id,
            ),
        )
    ]


def _concept_ref_payload(concept: Concept | None, fallback_id: str) -> dict[str, Any]:
    if concept is None:
        return {"id": fallback_id, "ref": fallback_id, "name": None, "kind": None}
    return {
        "id": concept.id,
        "ref": concept.slug,
        "name": concept.name,
        "kind": concept.kind.value,
    }


def _expand_handles(*, concept: Concept, query: str) -> list[dict[str, Any]]:
    descriptions = {
        "claims": "Show definitions, behaviors, invariants, failure modes, usage notes, and open questions.",
        "relations": "Show related concepts and their predicates.",
        "groundings": "Show implementation, storage, tests, docs, and observability anchors.",
        "memory_links": "Show related Shellbrain memories by concept role.",
        "evidence": "Show evidence metadata behind this concept.",
    }
    handles = []
    for facet in AVAILABLE_FACETS[:MAX_EXPAND_HANDLES]:
        handles.append(
            {
                "facet": facet,
                "description": descriptions[facet],
                "read_payload": {
                    "query": query,
                    "expand": {
                        "concepts": {
                            "mode": "explicit",
                            "refs": [concept.slug],
                            "facets": [facet],
                        }
                    },
                },
            }
        )
    return handles


def _guidance_for_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No strong concept match found."
    return "Use expand payloads to request implementation, evidence, cases, or related concepts."


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."
