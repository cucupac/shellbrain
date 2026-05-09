"""Pure concept relation rules."""

from __future__ import annotations

from collections.abc import Sequence

from app.core.entities.concepts import (
    Concept,
    ConceptKind,
    ConceptRelation,
    ConceptRelationPredicate,
)


def validate_relation_shape(
    *,
    subject: Concept,
    predicate: ConceptRelationPredicate,
    object_concept: Concept,
) -> None:
    """Reject relation shapes that violate concept semantics."""

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
        subject.kind != ConceptKind.PROCESS
        or object_concept.kind != ConceptKind.PROCESS
    ):
        raise ValueError("precedes requires process -> process")
    if (
        predicate == ConceptRelationPredicate.CONSTRAINS
        and subject.kind != ConceptKind.RULE
    ):
        raise ValueError("constrains requires rule -> concept")


def validate_no_contains_cycle(
    *,
    contains_edges: Sequence[ConceptRelation],
    subject_id: str,
    object_id: str,
) -> None:
    """Reject a proposed contains edge when it would introduce a cycle."""

    children_by_parent: dict[str, set[str]] = {}
    for edge in contains_edges:
        children_by_parent.setdefault(edge.subject_concept_id, set()).add(
            edge.object_concept_id
        )
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
