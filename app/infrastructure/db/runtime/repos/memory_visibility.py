"""Shared memory visibility filters for retrieval and read-path queries."""

from __future__ import annotations

from typing import Any, Sequence

from app.core.policies.retrieval.ontology_semantics import POSITIVE_LIFECYCLE_STATUSES
from app.infrastructure.db.runtime.models.memories import memories


def visible_memory_filters(
    *,
    repo_id: str,
    include_global: bool,
    kinds: Sequence[str] | None,
) -> list[Any]:
    """Build the SQL filters that select repo-visible, non-negative memories."""

    scope_values = ["repo", "global"] if include_global else ["repo"]
    filters: list[Any] = [
        memories.c.repo_id == repo_id,
        memories.c.status.in_(list(POSITIVE_LIFECYCLE_STATUSES)),
        memories.c.scope.in_(scope_values),
    ]
    if kinds:
        filters.append(memories.c.kind.in_(list(kinds)))
    return filters
