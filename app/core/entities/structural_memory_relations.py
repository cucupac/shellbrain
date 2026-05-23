"""Core ontology for curated memory-to-memory structural assertions."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final

from app.core.entities.memories import (
    ConfidenceValue,
    MemoryKind,
    MemoryLifecycleActor,
    MemoryLifecycleStatus,
)


class StructuralMemoryRelationPredicate(str, Enum):
    """Curated structural predicates between concrete memories."""

    SOLVED_BY = "solved_by"
    FAILED_WITH = "failed_with"
    SUPERSEDED_BY = "superseded_by"
    EXPLAINED_BY_CHANGE = "explained_by_change"


STRUCTURAL_MEMORY_RELATION_PREDICATE_VALUES: Final[tuple[str, ...]] = tuple(
    predicate.value for predicate in StructuralMemoryRelationPredicate
)

_FACT_LIKE_MEMORY_KINDS: Final[frozenset[MemoryKind]] = frozenset(
    {
        MemoryKind.FACT,
        MemoryKind.PREFERENCE,
        MemoryKind.CHANGE,
    }
)


@dataclass(kw_only=True)
class StructuralMemoryRelation:
    """One truth-bearing curated structural relation between concrete memories."""

    id: str
    repo_id: str
    subject_memory_id: str
    predicate: StructuralMemoryRelationPredicate
    object_memory_id: str
    status: MemoryLifecycleStatus = MemoryLifecycleStatus.ACTIVE
    confidence: float | None = None
    observed_at: datetime | None = None
    validated_at: datetime | None = None
    invalidated_at: datetime | None = None
    superseded_by_id: str | None = None
    created_by: MemoryLifecycleActor = MemoryLifecycleActor.WORKER
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        self.predicate = StructuralMemoryRelationPredicate(self.predicate)
        self.status = MemoryLifecycleStatus(self.status)
        self.created_by = MemoryLifecycleActor(self.created_by)
        _require_non_empty(self.id, "id")
        _require_non_empty(self.repo_id, "repo_id")
        _require_non_empty(self.subject_memory_id, "subject_memory_id")
        _require_non_empty(self.object_memory_id, "object_memory_id")
        if self.subject_memory_id == self.object_memory_id:
            raise ValueError("structural memory relation endpoints must differ")
        if self.confidence is not None:
            self.confidence = ConfidenceValue(float(self.confidence)).value


def predicate_for_problem_link_kind(
    memory_kind: MemoryKind | str,
) -> StructuralMemoryRelationPredicate:
    """Return the structural predicate created for a linked problem memory."""

    normalized_kind = MemoryKind(memory_kind)
    if normalized_kind is MemoryKind.SOLUTION:
        return StructuralMemoryRelationPredicate.SOLVED_BY
    if normalized_kind is MemoryKind.FAILED_TACTIC:
        return StructuralMemoryRelationPredicate.FAILED_WITH
    raise ValueError(f"unsupported problem-link memory kind: {memory_kind}")


def validate_structural_memory_relation_kinds(
    *,
    predicate: StructuralMemoryRelationPredicate | str,
    subject_kind: MemoryKind | str,
    object_kind: MemoryKind | str,
) -> None:
    """Validate one structural relation's allowed memory-kind shape."""

    normalized_predicate = StructuralMemoryRelationPredicate(predicate)
    normalized_subject = MemoryKind(subject_kind)
    normalized_object = MemoryKind(object_kind)
    if normalized_predicate is StructuralMemoryRelationPredicate.SOLVED_BY:
        _require_shape(
            normalized_predicate,
            normalized_subject,
            normalized_object,
            expected_subject=MemoryKind.PROBLEM,
            expected_object=MemoryKind.SOLUTION,
        )
        return
    if normalized_predicate is StructuralMemoryRelationPredicate.FAILED_WITH:
        _require_shape(
            normalized_predicate,
            normalized_subject,
            normalized_object,
            expected_subject=MemoryKind.PROBLEM,
            expected_object=MemoryKind.FAILED_TACTIC,
        )
        return
    if normalized_predicate is StructuralMemoryRelationPredicate.SUPERSEDED_BY:
        if (
            normalized_subject not in _FACT_LIKE_MEMORY_KINDS
            or normalized_object not in _FACT_LIKE_MEMORY_KINDS
        ):
            raise ValueError(
                "superseded_by requires fact/preference/change -> "
                "fact/preference/change"
            )
        return
    if normalized_predicate is StructuralMemoryRelationPredicate.EXPLAINED_BY_CHANGE:
        if (
            normalized_subject not in _FACT_LIKE_MEMORY_KINDS
            or normalized_object is not MemoryKind.CHANGE
        ):
            raise ValueError(
                "explained_by_change requires fact/preference/change -> change"
            )
        return
    raise ValueError(f"unsupported structural memory relation: {predicate}")


def _require_shape(
    predicate: StructuralMemoryRelationPredicate,
    subject_kind: MemoryKind,
    object_kind: MemoryKind,
    *,
    expected_subject: MemoryKind,
    expected_object: MemoryKind,
) -> None:
    if subject_kind is expected_subject and object_kind is expected_object:
        return
    raise ValueError(
        f"{predicate.value} requires {expected_subject.value} -> "
        f"{expected_object.value}; got {subject_kind.value} -> {object_kind.value}"
    )


def _require_non_empty(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"structural memory relation {name} must be non-empty")
