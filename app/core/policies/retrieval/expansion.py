"""Pure explicit read-expansion decisions."""

from __future__ import annotations

from typing import Any, Sequence

from app.core.policies.retrieval.ontology_semantics import (
    structural_relation_expansion_type,
)


def select_structural_memory_relation_neighbors(
    rows: Sequence[dict[str, Any]],
    *,
    anchor_memory_id: str,
) -> list[dict[str, Any]]:
    """Return visible structural relation neighbors for one anchor."""

    neighbors: dict[str, dict[str, Any]] = {}
    for row in rows:
        visible_memory_ids = {
            str(memory_id) for memory_id in row.get("visible_memory_ids", ())
        }
        for candidate_id in (
            str(row["subject_memory_id"]),
            str(row["object_memory_id"]),
        ):
            if (
                candidate_id == anchor_memory_id
                or candidate_id not in visible_memory_ids
            ):
                continue
            neighbors[candidate_id] = {
                "memory_id": candidate_id,
                "relation_type": str(row["predicate"]),
                "expansion_type": structural_relation_expansion_type(row["predicate"]),
            }
    return [neighbors[memory_id] for memory_id in sorted(neighbors)]
