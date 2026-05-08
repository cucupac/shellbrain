"""Use-case orchestration for the JSON-first concept endpoint."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.contracts.concepts import (
    AddClaimAction,
    AddGroundingAction,
    AddRelationAction,
    ConceptCommandRequest,
    ConceptEvidencePayload,
    LinkMemoryAction,
    UpsertAnchorAction,
    UpsertConceptAction,
)
from app.core.contracts.responses import OperationResult
from app.core.entities.concepts import (
    Anchor,
    AnchorKind,
    Concept,
    ConceptClaim,
    ConceptClaimType,
    ConceptCreatedBy,
    ConceptEvidence,
    ConceptEvidenceKind,
    ConceptEvidenceTargetType,
    ConceptGrounding,
    ConceptGroundingRole,
    ConceptKind,
    ConceptLifecycle,
    ConceptMemoryLink,
    ConceptMemoryLinkRole,
    ConceptRelation,
    ConceptRelationPredicate,
    ConceptSourceKind,
    ConceptStatus,
)
from app.core.entities.memory import MemoryScope
from app.core.interfaces.unit_of_work import IUnitOfWork


def execute_concept_command(request: ConceptCommandRequest, uow: IUnitOfWork) -> OperationResult:
    """Execute one concept endpoint request inside an active unit of work."""

    if request.mode == "show":
        assert request.concept is not None
        bundle = uow.concepts.get_concept_bundle(repo_id=request.repo_id, concept_ref=request.concept)
        if bundle is None:
            raise ValueError(f"Concept not found: {request.concept}")
        return OperationResult(status="ok", data={"concept": _serialize_concept_bundle(bundle, include=set(request.include))})

    assert request.actions is not None
    results: list[dict[str, Any]] = []
    for action in request.actions:
        if isinstance(action, UpsertConceptAction):
            results.append(_apply_upsert_concept(request.repo_id, action, uow))
        elif isinstance(action, AddRelationAction):
            results.append(_apply_add_relation(request.repo_id, action, uow))
        elif isinstance(action, AddClaimAction):
            results.append(_apply_add_claim(request.repo_id, action, uow))
        elif isinstance(action, UpsertAnchorAction):
            results.append(_apply_upsert_anchor(request.repo_id, action, uow))
        elif isinstance(action, AddGroundingAction):
            results.append(_apply_add_grounding(request.repo_id, action, uow))
        elif isinstance(action, LinkMemoryAction):
            results.append(_apply_link_memory(request.repo_id, action, uow))
        else:  # pragma: no cover - discriminated contract should make this impossible.
            raise ValueError(f"Unsupported concept action type: {getattr(action, 'type', '<unknown>')}")
    return OperationResult(status="ok", data={"applied_count": len(results), "results": results})


def _apply_upsert_concept(repo_id: str, action: UpsertConceptAction, uow: IUnitOfWork) -> dict[str, Any]:
    concept = uow.concepts.upsert_concept(
        Concept(
            id=str(uuid4()),
            repo_id=repo_id,
            slug=_normalize_slug(action.slug),
            name=action.name,
            kind=ConceptKind(action.kind),
            status=ConceptStatus(action.status),
            scope_note=action.scope_note,
        ),
        aliases=action.aliases,
    )
    return {"type": action.type, "concept_id": concept.id, "slug": concept.slug}


def _apply_add_relation(repo_id: str, action: AddRelationAction, uow: IUnitOfWork) -> dict[str, Any]:
    subject = _require_concept(repo_id, action.subject, uow)
    object_concept = _require_concept(repo_id, action.object, uow)
    _validate_relation_shape(
        repo_id=repo_id,
        subject=subject,
        predicate=ConceptRelationPredicate(action.predicate),
        object_concept=object_concept,
        uow=uow,
    )
    relation = uow.concepts.add_relation(
        ConceptRelation(
            id=str(uuid4()),
            repo_id=repo_id,
            subject_concept_id=subject.id,
            predicate=ConceptRelationPredicate(action.predicate),
            object_concept_id=object_concept.id,
            lifecycle=_lifecycle_from_action(action),
        )
    )
    _attach_evidence(repo_id, ConceptEvidenceTargetType.RELATION, relation.id, action.evidence, uow)
    return {"type": action.type, "relation_id": relation.id}


def _apply_add_claim(repo_id: str, action: AddClaimAction, uow: IUnitOfWork) -> dict[str, Any]:
    concept = _require_concept(repo_id, action.concept, uow)
    claim = uow.concepts.add_claim(
        ConceptClaim(
            id=str(uuid4()),
            repo_id=repo_id,
            concept_id=concept.id,
            claim_type=ConceptClaimType(action.claim_type),
            text=action.text,
            normalized_text=_normalize_text(action.text),
            lifecycle=_lifecycle_from_action(action),
        )
    )
    _attach_evidence(repo_id, ConceptEvidenceTargetType.CLAIM, claim.id, action.evidence, uow)
    return {"type": action.type, "claim_id": claim.id}


def _apply_upsert_anchor(repo_id: str, action: UpsertAnchorAction, uow: IUnitOfWork) -> dict[str, Any]:
    anchor = _upsert_anchor_from_payload(repo_id, action.kind, action.locator, uow)
    return {"type": action.type, "anchor_id": anchor.id, "canonical_locator_hash": anchor.canonical_locator_hash}


def _apply_add_grounding(repo_id: str, action: AddGroundingAction, uow: IUnitOfWork) -> dict[str, Any]:
    concept = _require_concept(repo_id, action.concept, uow)
    if action.anchor.id:
        anchor = uow.concepts.get_anchor(repo_id=repo_id, anchor_id=action.anchor.id)
        if anchor is None:
            raise ValueError(f"Anchor not found: {action.anchor.id}")
    else:
        assert action.anchor.kind is not None and action.anchor.locator is not None
        anchor = _upsert_anchor_from_payload(repo_id, action.anchor.kind, action.anchor.locator, uow)
    grounding = uow.concepts.add_grounding(
        ConceptGrounding(
            id=str(uuid4()),
            repo_id=repo_id,
            concept_id=concept.id,
            role=ConceptGroundingRole(action.role),
            anchor_id=anchor.id,
            lifecycle=_lifecycle_from_action(action),
        )
    )
    _attach_evidence(repo_id, ConceptEvidenceTargetType.GROUNDING, grounding.id, action.evidence, uow)
    return {"type": action.type, "grounding_id": grounding.id, "anchor_id": anchor.id}


def _apply_link_memory(repo_id: str, action: LinkMemoryAction, uow: IUnitOfWork) -> dict[str, Any]:
    concept = _require_concept(repo_id, action.concept, uow)
    memory = uow.memories.get(action.memory_id)
    if memory is None:
        raise ValueError(f"Memory not found: {action.memory_id}")
    if memory.repo_id != repo_id and memory.scope != MemoryScope.GLOBAL:
        raise ValueError(f"Memory is not visible for repo {repo_id}: {action.memory_id}")
    memory_link = uow.concepts.add_memory_link(
        ConceptMemoryLink(
            id=str(uuid4()),
            repo_id=repo_id,
            concept_id=concept.id,
            role=ConceptMemoryLinkRole(action.role),
            memory_id=memory.id,
            lifecycle=_lifecycle_from_action(action),
        )
    )
    _attach_evidence(repo_id, ConceptEvidenceTargetType.MEMORY_LINK, memory_link.id, action.evidence, uow)
    return {"type": action.type, "memory_link_id": memory_link.id}


def _lifecycle_from_action(action) -> ConceptLifecycle:
    """Build shared lifecycle fields from an action with lifecycle attributes."""

    return ConceptLifecycle(
        confidence=float(action.confidence),
        observed_at=action.observed_at,
        validated_at=action.validated_at,
        source_kind=ConceptSourceKind(action.source_kind) if action.source_kind is not None else None,
        source_ref=action.source_ref,
        created_by=ConceptCreatedBy(action.created_by),
    )


def _upsert_anchor_from_payload(repo_id: str, kind: str, locator: dict[str, Any], uow: IUnitOfWork) -> Anchor:
    canonical_hash = _canonical_locator_hash(kind=kind, locator=locator)
    return uow.concepts.upsert_anchor(
        Anchor(
            id=str(uuid4()),
            repo_id=repo_id,
            kind=AnchorKind(kind),
            locator_json=dict(locator),
            canonical_locator_hash=canonical_hash,
        )
    )


def _attach_evidence(
    repo_id: str,
    target_type: ConceptEvidenceTargetType,
    target_id: str,
    evidence_items: list[ConceptEvidencePayload],
    uow: IUnitOfWork,
) -> None:
    for item in evidence_items:
        _validate_evidence_visibility(repo_id, item, uow)
        uow.concepts.add_evidence(
            ConceptEvidence(
                id=str(uuid4()),
                repo_id=repo_id,
                target_type=target_type,
                target_id=target_id,
                evidence_kind=ConceptEvidenceKind(item.kind),
                anchor_id=item.anchor_id,
                memory_id=item.memory_id,
                commit_ref=item.commit_ref,
                transcript_ref=item.transcript_ref,
                note=item.note,
            )
        )


def _validate_evidence_visibility(repo_id: str, item: ConceptEvidencePayload, uow: IUnitOfWork) -> None:
    """Validate local references used by inline evidence."""

    if item.anchor_id and uow.concepts.get_anchor(repo_id=repo_id, anchor_id=item.anchor_id) is None:
        raise ValueError(f"Evidence anchor not found: {item.anchor_id}")
    if item.memory_id:
        memory = uow.memories.get(item.memory_id)
        if memory is None:
            raise ValueError(f"Evidence memory not found: {item.memory_id}")
        if memory.repo_id != repo_id and memory.scope != MemoryScope.GLOBAL:
            raise ValueError(f"Evidence memory is not visible for repo {repo_id}: {item.memory_id}")


def _require_concept(repo_id: str, concept_ref: str, uow: IUnitOfWork) -> Concept:
    concept = uow.concepts.get_concept_by_ref(repo_id=repo_id, concept_ref=_normalize_slug(concept_ref))
    if concept is None:
        concept = uow.concepts.get_concept_by_ref(repo_id=repo_id, concept_ref=concept_ref)
    if concept is None:
        raise ValueError(f"Concept not found: {concept_ref}")
    return concept


def _validate_relation_shape(
    *,
    repo_id: str,
    subject: Concept,
    predicate: ConceptRelationPredicate,
    object_concept: Concept,
    uow: IUnitOfWork,
) -> None:
    """Enforce semantic relation-shape rules that are too contextual for DB checks."""

    if subject.id == object_concept.id:
        raise ValueError("Concept relation cannot self-reference")
    if predicate == ConceptRelationPredicate.INVOLVES and object_concept.kind not in {
        ConceptKind.ENTITY,
        ConceptKind.COMPONENT,
        ConceptKind.RULE,
        ConceptKind.PROCESS,
    }:
        raise ValueError("involves object must be entity, component, rule, or process")
    if predicate == ConceptRelationPredicate.PRECEDES and (
        subject.kind != ConceptKind.PROCESS or object_concept.kind != ConceptKind.PROCESS
    ):
        raise ValueError("precedes requires process -> process")
    if predicate == ConceptRelationPredicate.CONSTRAINS and subject.kind != ConceptKind.RULE:
        raise ValueError("constrains requires rule -> concept")
    if predicate == ConceptRelationPredicate.CONTAINS:
        _validate_no_contains_cycle(repo_id=repo_id, subject_id=subject.id, object_id=object_concept.id, uow=uow)


def _validate_no_contains_cycle(*, repo_id: str, subject_id: str, object_id: str, uow: IUnitOfWork) -> None:
    """Reject contains edges that would introduce a cycle."""

    children_by_parent: dict[str, set[str]] = {}
    for edge in uow.concepts.list_contains_edges(repo_id=repo_id):
        children_by_parent.setdefault(edge.subject_concept_id, set()).add(edge.object_concept_id)
    children_by_parent.setdefault(subject_id, set()).add(object_id)
    stack = [object_id]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current == subject_id:
            raise ValueError("contains relation would create a cycle")
        if current in seen:
            continue
        seen.add(current)
        stack.extend(children_by_parent.get(current, set()))


def _serialize_concept_bundle(bundle: dict[str, Any], *, include: set[str]) -> dict[str, Any]:
    concept: Concept = bundle["concept"]
    aliases = [_alias_to_payload(alias) for alias in bundle["aliases"]]
    relations = [_relation_to_payload(relation) for relation in bundle["relations"]]
    claims = [_claim_to_payload(claim) for claim in bundle["claims"]]
    anchors_by_id = {anchor.id: _anchor_to_payload(anchor) for anchor in bundle["anchors"]}
    groundings = [_grounding_to_payload(grounding, anchors_by_id) for grounding in bundle["groundings"]]
    memory_links = [_memory_link_to_payload(memory_link) for memory_link in bundle["memory_links"]]
    evidence_counts = _evidence_counts(bundle["evidence"])
    payload: dict[str, Any] = {
        "id": concept.id,
        "repo_id": concept.repo_id,
        "slug": concept.slug,
        "name": concept.name,
        "kind": concept.kind.value,
        "status": concept.status.value,
        "aliases": aliases,
        "status_rollup": _status_rollup(relations, claims, groundings, memory_links),
        "evidence_counts": evidence_counts,
    }
    if "relations" in include:
        payload["relations"] = relations
    if "claims" in include:
        payload["claims"] = claims
    if "groundings" in include:
        payload["groundings"] = groundings
    if "memory_links" in include:
        payload["memory_links"] = memory_links
    if "preview_concept" in include:
        payload["preview_concept"] = _preview_concept(concept=concept, claims=claims, relations=relations, groundings=groundings, memory_links=memory_links)
    return payload


def _alias_to_payload(alias) -> dict[str, Any]:
    return {"alias": alias.alias, "normalized_alias": alias.normalized_alias}


def _relation_to_payload(relation: ConceptRelation) -> dict[str, Any]:
    return {
        "id": relation.id,
        "subject_concept_id": relation.subject_concept_id,
        "predicate": relation.predicate.value,
        "object_concept_id": relation.object_concept_id,
        **_lifecycle_payload(relation.lifecycle),
    }


def _claim_to_payload(claim: ConceptClaim) -> dict[str, Any]:
    return {
        "id": claim.id,
        "concept_id": claim.concept_id,
        "claim_type": claim.claim_type.value,
        "text": claim.text,
        **_lifecycle_payload(claim.lifecycle),
    }


def _grounding_to_payload(grounding: ConceptGrounding, anchors_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": grounding.id,
        "concept_id": grounding.concept_id,
        "role": grounding.role.value,
        "anchor_id": grounding.anchor_id,
        "anchor": anchors_by_id.get(grounding.anchor_id),
        **_lifecycle_payload(grounding.lifecycle),
    }


def _memory_link_to_payload(memory_link: ConceptMemoryLink) -> dict[str, Any]:
    return {
        "id": memory_link.id,
        "concept_id": memory_link.concept_id,
        "role": memory_link.role.value,
        "memory_id": memory_link.memory_id,
        **_lifecycle_payload(memory_link.lifecycle),
    }


def _anchor_to_payload(anchor: Anchor) -> dict[str, Any]:
    return {
        "id": anchor.id,
        "kind": anchor.kind.value,
        "locator": anchor.locator_json,
        "canonical_locator_hash": anchor.canonical_locator_hash,
        "status": anchor.status.value,
    }


def _lifecycle_payload(lifecycle: ConceptLifecycle) -> dict[str, Any]:
    return {
        "status": lifecycle.status.value,
        "confidence": lifecycle.confidence,
        "observed_at": _iso(lifecycle.observed_at),
        "validated_at": _iso(lifecycle.validated_at),
        "source_kind": lifecycle.source_kind.value if lifecycle.source_kind else None,
        "source_ref": lifecycle.source_ref,
        "superseded_by_id": lifecycle.superseded_by_id,
        "created_by": lifecycle.created_by.value,
    }


def _evidence_counts(evidence_items: list[ConceptEvidence]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in evidence_items:
        key = f"{item.target_type.value}:{item.target_id}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _status_rollup(*record_groups: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for group in record_groups:
        for item in group:
            status = str(item.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
    return counts


def _preview_concept(
    *,
    concept: Concept,
    claims: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    groundings: list[dict[str, Any]],
    memory_links: list[dict[str, Any]],
) -> dict[str, Any]:
    definition = next((claim["text"] for claim in claims if claim["claim_type"] == "definition" and claim["status"] == "active"), None)
    return {
        "name": concept.name,
        "kind": concept.kind.value,
        "orientation": definition or f"{concept.name} is a {concept.kind.value} concept.",
        "relation_count": len(relations),
        "claim_count": len(claims),
        "grounding_count": len(groundings),
        "memory_link_count": len(memory_links),
    }


def _canonical_locator_hash(*, kind: str, locator: dict[str, Any]) -> str:
    serialized = json.dumps({"kind": kind, "locator": locator}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _normalize_slug(value: str) -> str:
    return "-".join(_normalize_text(value).replace("_", "-").split())


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
