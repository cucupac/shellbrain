"""Concept-context rendering for normal read packs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from app.core.entities.settings import ThresholdSettings, default_threshold_settings
from app.core.use_cases.retrieval.read.request import (
    MemoryReadRequest,
    ReadConceptsExpandRequest,
)
from app.core.entities.concepts import (
    Concept,
    ConceptClaim,
    ConceptLifecycleStatus,
)
from app.core.ports.db.concept_repositories import IConceptsRepo
from app.core.ports.db.retrieval_repositories import (
    IConceptKeywordRetrievalRepo,
    IConceptSemanticRetrievalRepo,
)
from app.core.policies.retrieval.ontology_semantics import (
    bundle_lifecycle_statuses,
    is_active_lifecycle,
    lifecycle_retrieval_multiplier,
    lifecycle_status_counts,
)
from app.core.use_cases.retrieval.concept_seed_retrieval import retrieve_concept_seeds


AVAILABLE_FACETS = ("claims", "relations", "groundings", "memory_links", "evidence")
MAX_KEY_CLAIMS = 3
MAX_ORIENTATION_CHARS = 600


def append_concepts_to_pack(
    *,
    pack: dict[str, Any],
    request: MemoryReadRequest,
    concepts: IConceptsRepo,
    concept_keyword_retrieval: IConceptKeywordRetrievalRepo | None = None,
    concept_semantic_retrieval: IConceptSemanticRetrievalRepo | None = None,
    query_vector: Sequence[float] = (),
    query_model: str | None = None,
    threshold_settings: ThresholdSettings | None = None,
) -> dict[str, Any]:
    """Append the stable concept-context section to one read pack."""

    concept_expand = (
        ReadConceptsExpandRequest()
        if request.expand is None
        else request.expand.concepts
    )
    if concept_expand.mode == "none":
        pack["concepts"] = {
            "mode": "none",
            "items": [],
            "guidance": "Concept context suppressed by request.",
        }
        return pack

    items = _auto_concept_items(
        pack=pack,
        request=request,
        concept_expand=concept_expand,
        concepts=concepts,
        concept_keyword_retrieval=concept_keyword_retrieval,
        concept_semantic_retrieval=concept_semantic_retrieval,
        query_vector=query_vector,
        query_model=query_model,
        threshold_settings=threshold_settings or default_threshold_settings(),
    )
    pack["concepts"] = {
        "mode": "auto",
        "items": items,
        "guidance": _guidance_for_items(items),
    }
    return pack


def _auto_concept_items(
    *,
    pack: dict[str, Any],
    request: MemoryReadRequest,
    concept_expand: ReadConceptsExpandRequest,
    concepts: IConceptsRepo,
    concept_keyword_retrieval: IConceptKeywordRetrievalRepo | None,
    concept_semantic_retrieval: IConceptSemanticRetrievalRepo | None,
    query_vector: Sequence[float],
    query_model: str | None,
    threshold_settings: ThresholdSettings,
) -> list[dict[str, Any]]:
    memory_ids = _pack_memory_ids(pack)
    candidates: dict[str, dict[str, Any]] = {}

    for link_match in concepts.find_concepts_for_memory_ids(
        repo_id=request.repo_id, memory_ids=memory_ids
    ):
        concept_id = str(link_match["concept_id"])
        status = _required_string(link_match, "status", "concept memory link")
        confidence = _required_float(link_match, "confidence", "concept memory link")
        multiplier = lifecycle_retrieval_multiplier(status)
        if multiplier <= 0:
            continue
        candidate = candidates.setdefault(concept_id, {"score": 0.0, "why": []})
        candidate["score"] += 10.0 * multiplier * max(confidence, 0.1)
        _append_linked_memory_reason(candidate["why"], link_match)

    _add_retrieved_concept_candidates(
        candidates,
        request=request,
        concept_keyword_retrieval=concept_keyword_retrieval,
        concept_semantic_retrieval=concept_semantic_retrieval,
        query_vector=query_vector,
        query_model=query_model,
        threshold_settings=threshold_settings,
    )

    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for concept_id, candidate in candidates.items():
        bundle = concepts.get_concept_bundle(
            repo_id=request.repo_id, concept_ref=concept_id
        )
        if bundle is None or bundle["concept"].status.value != "active":
            continue
        score = float(candidate["score"])
        if score <= 0:
            continue
        ranked.append(
            (score, str(bundle["concept"].slug), {**candidate, "bundle": bundle})
        )
    ranked.sort(key=lambda item: (-item[0], item[1]))

    items: list[dict[str, Any]] = []
    for _, _, candidate in ranked[: concept_expand.max_auto]:
        items.append(
            _render_concept_item(
                bundle=candidate["bundle"],
                why_matched=candidate["why"],
            )
        )
    return items


def _add_retrieved_concept_candidates(
    candidates: dict[str, dict[str, Any]],
    *,
    request: MemoryReadRequest,
    concept_keyword_retrieval: IConceptKeywordRetrievalRepo | None,
    concept_semantic_retrieval: IConceptSemanticRetrievalRepo | None,
    query_vector: Sequence[float],
    query_model: str | None,
    threshold_settings: ThresholdSettings,
) -> None:
    seeds = retrieve_concept_seeds(
        request.model_dump(mode="python"),
        concept_keyword_retrieval=concept_keyword_retrieval,
        concept_semantic_retrieval=concept_semantic_retrieval,
        query_vector=query_vector,
        query_model=query_model,
        thresholds=threshold_settings,
        limit=20,
    )
    for retrieved in seeds["fused"]:
        concept_id = str(retrieved["concept_id"])
        candidate = candidates.setdefault(concept_id, {"score": 0.0, "why": []})
        candidate["score"] += 20.0 * _required_float(
            retrieved, "rrf_score", "concept retrieval match"
        )
        _append_retrieval_reasons(candidate["why"], retrieved)


def _render_concept_item(
    *,
    bundle: dict[str, Any],
    why_matched: list[dict[str, Any]],
) -> dict[str, Any]:
    concept: Concept = bundle["concept"]
    claims: list[ConceptClaim] = list(bundle["claims"])
    item: dict[str, Any] = {
        "ref": concept.slug,
        "id": concept.id,
        "name": concept.name,
        "kind": concept.kind.value,
        "status": concept.status.value,
        "created_at": _iso(concept.created_at),
        "updated_at": _iso(concept.updated_at),
        "orientation": _orientation(concept, claims),
        "why_matched": why_matched,
        "freshness": _freshness(bundle),
        "key_claims": _key_claims(claims),
        "available_facets": list(AVAILABLE_FACETS),
    }
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
    role = _required_string(link_match, "role", "concept memory link")
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


def _append_retrieval_reasons(
    reasons: list[dict[str, Any]], retrieved: dict[str, Any]
) -> None:
    if retrieved.get("rank_keyword") is not None:
        _append_rank_reason(
            reasons,
            reason="concept_keyword",
            rank=int(retrieved["rank_keyword"]),
        )
    if retrieved.get("rank_semantic") is not None:
        _append_rank_reason(
            reasons,
            reason="concept_semantic",
            rank=int(retrieved["rank_semantic"]),
        )


def _append_rank_reason(
    reasons: list[dict[str, Any]], *, reason: str, rank: int
) -> None:
    if any(
        item.get("reason") == reason and item.get("rank") == rank for item in reasons
    ):
        return
    reasons.append({"reason": reason, "rank": rank})


def _required_string(record: dict[str, Any], field: str, record_type: str) -> str:
    """Return a required non-empty string from ranking evidence."""

    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{record_type} is missing required {field}")
    return value.strip()


def _required_float(record: dict[str, Any], field: str, record_type: str) -> float:
    """Return a required numeric field from ranking evidence."""

    if field not in record or record[field] is None:
        raise ValueError(f"{record_type} is missing required {field}")
    return float(record[field])


def _freshness(bundle: dict[str, Any]) -> dict[str, Any]:
    statuses = bundle_lifecycle_statuses(bundle)
    counts = lifecycle_status_counts(statuses)
    maybe_stale = counts.get(ConceptLifecycleStatus.MAYBE_STALE.value, 0)
    stale = counts.get(ConceptLifecycleStatus.STALE.value, 0)
    wrong = counts.get(ConceptLifecycleStatus.WRONG.value, 0)
    superseded = counts.get(ConceptLifecycleStatus.SUPERSEDED.value, 0)
    archived = counts.get(ConceptLifecycleStatus.ARCHIVED.value, 0)
    return {
        "active_records": counts.get(ConceptLifecycleStatus.ACTIVE.value, 0),
        "maybe_stale_records": maybe_stale,
        "stale_records": stale,
        "superseded_records": superseded,
        "wrong_records": wrong,
        "archived_records": archived,
    }


def _orientation(concept: Concept, claims: list[ConceptClaim]) -> str:
    definition = next(
        (
            claim.text
            for claim in _sort_claims(claims)
            if claim.claim_type.value == "definition"
            and is_active_lifecycle(claim.lifecycle.status)
        ),
        None,
    )
    text = definition or f"{concept.name} is a {concept.kind.value} concept."
    return _truncate(text, MAX_ORIENTATION_CHARS)


def _key_claims(claims: list[ConceptClaim]) -> list[dict[str, Any]]:
    active_claims = [
        claim
        for claim in _sort_claims(claims)
        if is_active_lifecycle(claim.lifecycle.status)
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
        "observed_at": _iso(claim.lifecycle.observed_at),
        "validated_at": _iso(claim.lifecycle.validated_at),
        "created_at": _iso(claim.created_at),
        "updated_at": _iso(claim.updated_at),
    }


def _guidance_for_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No strong concept match found."
    return "Use concept show with a concept ref and include facets for details and evidence."


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
