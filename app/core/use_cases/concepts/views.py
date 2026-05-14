"""Concept response views."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.entities.concepts import (
    Anchor,
    Concept,
    ConceptClaim,
    ConceptEvidence,
    ConceptGrounding,
    ConceptLifecycle,
    ConceptMemoryLink,
    ConceptRelation,
)


def serialize_concept_bundle(
    bundle: dict[str, Any], *, include: set[str]
) -> dict[str, Any]:
    """Serialize one repo concept bundle for command responses."""

    concept: Concept = bundle["concept"]
    aliases = [_alias_to_payload(alias) for alias in bundle["aliases"]]
    relations = [_relation_to_payload(relation) for relation in bundle["relations"]]
    claims = [_claim_to_payload(claim) for claim in bundle["claims"]]
    anchors_by_id = {
        anchor.id: _anchor_to_payload(anchor) for anchor in bundle["anchors"]
    }
    groundings = [
        _grounding_to_payload(grounding, anchors_by_id)
        for grounding in bundle["groundings"]
    ]
    memory_links = [
        _memory_link_to_payload(memory_link) for memory_link in bundle["memory_links"]
    ]
    evidence_counts = _evidence_counts(bundle["evidence"])

    payload: dict[str, Any] = {
        "id": concept.id,
        "repo_id": concept.repo_id,
        "slug": concept.slug,
        "name": concept.name,
        "kind": concept.kind.value,
        "status": concept.status.value,
        "created_at": _iso(concept.created_at),
        "updated_at": _iso(concept.updated_at),
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
        payload["preview_concept"] = _preview_concept(
            concept=concept,
            claims=claims,
            relations=relations,
            groundings=groundings,
            memory_links=memory_links,
        )
    return payload


def _alias_to_payload(alias) -> dict[str, Any]:
    return {
        "alias": alias.alias,
        "normalized_alias": alias.normalized_alias,
        "created_at": _iso(alias.created_at),
    }


def _relation_to_payload(relation: ConceptRelation) -> dict[str, Any]:
    return {
        "id": relation.id,
        "subject_concept_id": relation.subject_concept_id,
        "predicate": relation.predicate.value,
        "object_concept_id": relation.object_concept_id,
        "created_at": _iso(relation.created_at),
        "updated_at": _iso(relation.updated_at),
        **_lifecycle_payload(relation.lifecycle),
    }


def _claim_to_payload(claim: ConceptClaim) -> dict[str, Any]:
    return {
        "id": claim.id,
        "concept_id": claim.concept_id,
        "claim_type": claim.claim_type.value,
        "text": claim.text,
        "created_at": _iso(claim.created_at),
        "updated_at": _iso(claim.updated_at),
        **_lifecycle_payload(claim.lifecycle),
    }


def _grounding_to_payload(
    grounding: ConceptGrounding, anchors_by_id: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    return {
        "id": grounding.id,
        "concept_id": grounding.concept_id,
        "role": grounding.role.value,
        "anchor_id": grounding.anchor_id,
        "anchor": anchors_by_id.get(grounding.anchor_id),
        "created_at": _iso(grounding.created_at),
        "updated_at": _iso(grounding.updated_at),
        **_lifecycle_payload(grounding.lifecycle),
    }


def _memory_link_to_payload(memory_link: ConceptMemoryLink) -> dict[str, Any]:
    return {
        "id": memory_link.id,
        "concept_id": memory_link.concept_id,
        "role": memory_link.role.value,
        "memory_id": memory_link.memory_id,
        "created_at": _iso(memory_link.created_at),
        "updated_at": _iso(memory_link.updated_at),
        **_lifecycle_payload(memory_link.lifecycle),
    }


def _anchor_to_payload(anchor: Anchor) -> dict[str, Any]:
    return {
        "id": anchor.id,
        "kind": anchor.kind.value,
        "locator": anchor.locator_json,
        "canonical_locator_hash": anchor.canonical_locator_hash,
        "status": anchor.status.value,
        "created_at": _iso(anchor.created_at),
        "updated_at": _iso(anchor.updated_at),
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
    definition = next(
        (
            claim["text"]
            for claim in claims
            if claim["claim_type"] == "definition" and claim["status"] == "active"
        ),
        None,
    )
    return {
        "name": concept.name,
        "kind": concept.kind.value,
        "orientation": definition
        or f"{concept.name} is a {concept.kind.value} concept.",
        "relation_count": len(relations),
        "claim_count": len(claims),
        "grounding_count": len(groundings),
        "memory_link_count": len(memory_links),
    }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
