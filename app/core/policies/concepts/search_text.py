"""Pure concept aggregate text rendering for retrieval embeddings."""

from __future__ import annotations

from typing import Any

from app.core.entities.concepts import (
    Anchor,
    Concept,
    ConceptClaim,
    ConceptGrounding,
    ConceptLifecycleStatus,
    ConceptMemoryLink,
    ConceptRelation,
)


def build_concept_embedding_text(bundle: dict[str, Any]) -> str:
    """Render one concept bundle into deterministic aggregate retrieval text."""

    concept: Concept = bundle["concept"]
    parts: list[str] = [
        concept.slug,
        concept.name,
        concept.kind.value,
    ]
    if concept.scope_note:
        parts.append(concept.scope_note)
    parts.extend(
        alias.alias
        for alias in sorted(
            bundle.get("aliases", ()), key=lambda item: item.normalized_alias
        )
    )
    parts.extend(_claim_parts(bundle.get("claims", ())))
    parts.extend(_relation_parts(bundle.get("relations", ()), concept_id=concept.id))
    parts.extend(_grounding_parts(bundle.get("groundings", ()), bundle.get("anchors", ())))
    parts.extend(_memory_link_parts(bundle.get("memory_links", ())))
    return " ".join(_clean_parts(parts))


def _claim_parts(claims: list[ConceptClaim]) -> list[str]:
    parts: list[str] = []
    for claim in sorted(claims, key=lambda item: (item.claim_type.value, item.text)):
        if claim.lifecycle.status is not ConceptLifecycleStatus.ACTIVE:
            continue
        parts.extend((claim.claim_type.value, claim.text))
    return parts


def _relation_parts(
    relations: list[ConceptRelation], *, concept_id: str
) -> list[str]:
    parts: list[str] = []
    for relation in sorted(
        relations,
        key=lambda item: (
            item.predicate.value,
            item.subject_concept_id,
            item.object_concept_id,
        ),
    ):
        if relation.lifecycle.status is not ConceptLifecycleStatus.ACTIVE:
            continue
        neighbor_id = (
            relation.object_concept_id
            if relation.subject_concept_id == concept_id
            else relation.subject_concept_id
        )
        parts.extend((relation.predicate.value, neighbor_id))
    return parts


def _grounding_parts(
    groundings: list[ConceptGrounding], anchors: list[Anchor]
) -> list[str]:
    anchor_by_id = {anchor.id: anchor for anchor in anchors}
    parts: list[str] = []
    for grounding in sorted(
        groundings, key=lambda item: (item.role.value, item.anchor_id)
    ):
        if grounding.lifecycle.status is not ConceptLifecycleStatus.ACTIVE:
            continue
        anchor = anchor_by_id.get(grounding.anchor_id)
        parts.append(grounding.role.value)
        if anchor is not None:
            parts.append(anchor.kind.value)
            parts.extend(_locator_scalars(anchor.locator_json))
    return parts


def _memory_link_parts(memory_links: list[ConceptMemoryLink]) -> list[str]:
    parts: list[str] = []
    for link in sorted(memory_links, key=lambda item: (item.role.value, item.memory_id)):
        if link.lifecycle.status is not ConceptLifecycleStatus.ACTIVE:
            continue
        parts.extend((link.role.value, link.memory_id))
    return parts


def _locator_scalars(value: object) -> tuple[str, ...]:
    scalars: list[str] = []

    def _walk(item: object) -> None:
        if isinstance(item, dict):
            for key in sorted(item):
                _walk(item[key])
            return
        if isinstance(item, (list, tuple)):
            for nested in item:
                _walk(nested)
            return
        if item is None or isinstance(item, bool):
            return
        text = str(item).strip()
        if text:
            scalars.append(text)

    _walk(value)
    return tuple(scalars)


def _clean_parts(parts: list[str]) -> tuple[str, ...]:
    return tuple(part.strip() for part in parts if part and part.strip())
