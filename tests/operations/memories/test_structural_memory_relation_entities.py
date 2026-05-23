"""Core structural memory relation invariant tests."""

import pytest

from app.core.entities.memories import MemoryKind
from app.core.entities.structural_memory_relations import (
    StructuralMemoryRelation,
    StructuralMemoryRelationPredicate,
    validate_structural_memory_relation_kinds,
)


def test_structural_memory_relation_rejects_retired_predicates() -> None:
    """retired or generic predicates should not normalize into current ontology."""

    with pytest.raises(ValueError):
        StructuralMemoryRelation(
            id="relation-1",
            repo_id="repo-a",
            subject_memory_id="memory-a",
            predicate="matures_into",
            object_memory_id="memory-b",
        )


def test_structural_memory_relation_rejects_self_relations() -> None:
    """structural relations should always have distinct memory endpoints."""

    with pytest.raises(ValueError, match="endpoints must differ"):
        StructuralMemoryRelation(
            id="relation-1",
            repo_id="repo-a",
            subject_memory_id="memory-a",
            predicate=StructuralMemoryRelationPredicate.SUPERSEDED_BY,
            object_memory_id="memory-a",
        )


def test_structural_memory_relation_kind_rules_are_strict() -> None:
    """predicate validation should accept only the locked Phase 6 shapes."""

    validate_structural_memory_relation_kinds(
        predicate=StructuralMemoryRelationPredicate.SOLVED_BY,
        subject_kind=MemoryKind.PROBLEM,
        object_kind=MemoryKind.SOLUTION,
    )
    validate_structural_memory_relation_kinds(
        predicate=StructuralMemoryRelationPredicate.FAILED_WITH,
        subject_kind=MemoryKind.PROBLEM,
        object_kind=MemoryKind.FAILED_TACTIC,
    )
    validate_structural_memory_relation_kinds(
        predicate=StructuralMemoryRelationPredicate.SUPERSEDED_BY,
        subject_kind=MemoryKind.PREFERENCE,
        object_kind=MemoryKind.FACT,
    )
    validate_structural_memory_relation_kinds(
        predicate=StructuralMemoryRelationPredicate.EXPLAINED_BY_CHANGE,
        subject_kind=MemoryKind.CHANGE,
        object_kind=MemoryKind.CHANGE,
    )
    with pytest.raises(ValueError, match="solved_by requires"):
        validate_structural_memory_relation_kinds(
            predicate=StructuralMemoryRelationPredicate.SOLVED_BY,
            subject_kind=MemoryKind.FACT,
            object_kind=MemoryKind.SOLUTION,
        )
