"""Shared ontology interpretation rules for read and recall retrieval."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

from app.core.entities.memories import (
    DEFAULT_RETRIEVABLE_MEMORY_STATUS_VALUES,
    MemoryLifecycleStatus,
)


ACTIVE_STATUS = MemoryLifecycleStatus.ACTIVE.value
MAYBE_STALE_STATUS = MemoryLifecycleStatus.MAYBE_STALE.value
STALE_STATUS = MemoryLifecycleStatus.STALE.value
SUPERSEDED_STATUS = MemoryLifecycleStatus.SUPERSEDED.value
WRONG_STATUS = MemoryLifecycleStatus.WRONG.value
ARCHIVED_STATUS = MemoryLifecycleStatus.ARCHIVED.value

POSITIVE_LIFECYCLE_STATUSES = frozenset(DEFAULT_RETRIEVABLE_MEMORY_STATUS_VALUES)

LIFECYCLE_RETRIEVAL_MULTIPLIERS: Mapping[str, float] = {
    status.value: status.retrieval_multiplier for status in MemoryLifecycleStatus
}

CONCEPT_MEMORY_HIGH_SIGNAL_ROLES = frozenset(
    {
        "solution_for",
        "failed_tactic_for",
        "warns_about",
        "change_relevant_to",
    }
)
CONCEPT_MEMORY_WARNING_ROLES = frozenset({"failed_tactic_for", "warns_about"})
CONCEPT_MEMORY_CHANGE_ROLES = frozenset({"change_relevant_to"})

STRUCTURAL_PROBLEM_RELATION_PREDICATES = ("solved_by", "failed_with")
STRUCTURAL_FACT_UPDATE_RELATION_PREDICATES = (
    "superseded_by",
    "explained_by_change",
)

REVERSIBLE_ASSOCIATION_RELATION_TYPES = frozenset({"associated_with"})

_STRUCTURAL_EXPANSION_BY_PREDICATE = {
    "solved_by": "problem_attempt",
    "failed_with": "problem_attempt",
    "superseded_by": "fact_update",
    "explained_by_change": "fact_update",
}
_WHY_INCLUDED_BY_EXPANSION = {
    "problem_attempt": "problem_attempt",
    "fact_update": "fact_update",
    "association": "association_link",
}


def normalize_lifecycle_status(status: Any) -> str:
    """Return a normalized lifecycle status value or raise on unknown states."""

    value = str(getattr(status, "value", status))
    if value not in LIFECYCLE_RETRIEVAL_MULTIPLIERS:
        raise ValueError(f"unsupported lifecycle status: {value}")
    return value


def lifecycle_retrieval_multiplier(status: Any) -> float:
    """Return the default positive retrieval multiplier for one lifecycle status."""

    return LIFECYCLE_RETRIEVAL_MULTIPLIERS[normalize_lifecycle_status(status)]


def is_active_lifecycle(status: Any) -> bool:
    """Return whether a lifecycle status is active."""

    return normalize_lifecycle_status(status) == ACTIVE_STATUS


def lifecycle_status_counts(statuses: Iterable[Any]) -> dict[str, int]:
    """Return deterministic counts for all known lifecycle states."""

    counter = Counter(normalize_lifecycle_status(status) for status in statuses)
    return {
        status: counter[status]
        for status in (
            ACTIVE_STATUS,
            MAYBE_STALE_STATUS,
            STALE_STATUS,
            SUPERSEDED_STATUS,
            WRONG_STATUS,
            ARCHIVED_STATUS,
        )
        if counter[status]
    }


def bundle_lifecycle_statuses(bundle: Mapping[str, Any]) -> tuple[str, ...]:
    """Return lifecycle status values across every truth-bearing concept facet."""

    return tuple(
        record.lifecycle.status.value
        for key in ("claims", "relations", "groundings", "memory_links")
        for record in bundle[key]
    )


def lifecycle_currentness_payload(
    lifecycle: Any, *, active_reason: str, validated_reason: str
) -> dict[str, str]:
    """Return currentness text for one truth-bearing record lifecycle object."""

    status = normalize_lifecycle_status(lifecycle.status)
    if status == ACTIVE_STATUS:
        if getattr(lifecycle, "validated_at", None) is not None:
            return {"currentness": "current", "temporal_reason": validated_reason}
        return {"currentness": "current", "temporal_reason": active_reason}
    return {
        "currentness": status,
        "temporal_reason": f"lifecycle status is {status}",
    }


def memory_currentness_payload(
    *, status: Any, kind: Any, link_roles: Iterable[str]
) -> dict[str, str]:
    """Return currentness text for one concrete memory in a retrieval pack."""

    normalized_status = normalize_lifecycle_status(status)
    if normalized_status != ACTIVE_STATUS:
        return {
            "currentness": normalized_status,
            "temporal_reason": f"memory lifecycle status is {normalized_status}",
        }
    normalized_kind = str(getattr(kind, "value", kind))
    roles = {str(role) for role in link_roles}
    if roles & CONCEPT_MEMORY_CHANGE_ROLES:
        return {
            "currentness": "current",
            "temporal_reason": (
                "change_relevant_to link marks this memory as concept-evolution context"
            ),
        }
    if normalized_kind == "change":
        return {
            "currentness": "current",
            "temporal_reason": "change memory may supersede older guidance",
        }
    if roles & CONCEPT_MEMORY_WARNING_ROLES or normalized_kind == "failed_tactic":
        return {
            "currentness": "historical_warning",
            "temporal_reason": "failed tactic or warning should be treated as trap context",
        }
    return {
        "currentness": "current",
        "temporal_reason": "visible memory with no supersession signal in this pack",
    }


def structural_relation_expansion_type(predicate: Any) -> str:
    """Map canonical structural memory predicates to stable read expansion labels."""

    value = str(getattr(predicate, "value", predicate))
    try:
        return _STRUCTURAL_EXPANSION_BY_PREDICATE[value]
    except KeyError as exc:
        raise ValueError(
            f"unsupported structural memory relation predicate: {value}"
        ) from exc


def why_included_for_expansion(expansion_type: str) -> str:
    """Return the stable context-pack inclusion label for an expansion type."""

    try:
        return _WHY_INCLUDED_BY_EXPANSION[expansion_type]
    except KeyError as exc:
        raise ValueError(f"unsupported read expansion type: {expansion_type}") from exc
