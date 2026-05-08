"""Pure explicit read-expansion decisions."""

from __future__ import annotations

from typing import Any, Sequence


_REVERSIBLE_ASSOCIATION_TYPES = frozenset({"associated_with", "matures_into"})


def select_problem_attempt_neighbors(
    rows: Sequence[dict[str, Any]],
    *,
    anchor_memory_id: str,
) -> list[dict[str, Any]]:
    """Return visible problem-attempt neighbors for one anchor."""

    neighbors: dict[str, dict[str, Any]] = {}
    for row in rows:
        visible_memory_ids = {str(memory_id) for memory_id in row.get("visible_memory_ids", ())}
        for candidate_id in (str(row["problem_id"]), str(row["attempt_id"])):
            if candidate_id == anchor_memory_id or candidate_id not in visible_memory_ids:
                continue
            neighbors[candidate_id] = {"memory_id": candidate_id, "expansion_type": "problem_attempt"}
    return [neighbors[memory_id] for memory_id in sorted(neighbors)]


def select_fact_update_neighbors(
    rows: Sequence[dict[str, Any]],
    *,
    anchor_memory_id: str,
) -> list[dict[str, Any]]:
    """Return visible fact-update neighbors for one anchor."""

    neighbors: dict[str, dict[str, Any]] = {}
    for row in rows:
        visible_memory_ids = {str(memory_id) for memory_id in row.get("visible_memory_ids", ())}
        for candidate_id in (str(row["old_fact_id"]), str(row["change_id"]), str(row["new_fact_id"])):
            if candidate_id == anchor_memory_id or candidate_id not in visible_memory_ids:
                continue
            neighbors[candidate_id] = {"memory_id": candidate_id, "expansion_type": "fact_update"}
    return [neighbors[memory_id] for memory_id in sorted(neighbors)]


def select_association_neighbors(
    rows: Sequence[dict[str, Any]],
    *,
    anchor_memory_id: str,
    min_strength: float,
) -> list[dict[str, Any]]:
    """Return best visible association neighbors for one anchor."""

    best_by_memory_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        neighbor = _association_neighbor(row, anchor_memory_id=anchor_memory_id, min_strength=min_strength)
        if neighbor is None:
            continue
        memory_id = str(neighbor["memory_id"])
        strength = float(neighbor["strength"])
        relation_type = str(neighbor["relation_type"])
        current = best_by_memory_id.get(memory_id)
        if current is None or strength > float(current["strength"]) or (
            strength == float(current["strength"]) and relation_type < str(current["relation_type"])
        ):
            best_by_memory_id[memory_id] = neighbor
    return sorted(
        best_by_memory_id.values(),
        key=lambda item: (-float(item["strength"]), str(item["memory_id"]), str(item["relation_type"])),
    )


def _association_neighbor(
    row: dict[str, Any],
    *,
    anchor_memory_id: str,
    min_strength: float,
) -> dict[str, Any] | None:
    """Resolve whether one edge row yields a traversable association neighbor."""

    strength = float(row["strength"])
    if strength < min_strength:
        return None
    from_memory_id = str(row["from_memory_id"])
    to_memory_id = str(row["to_memory_id"])
    relation_type = str(row["relation_type"])
    if from_memory_id == anchor_memory_id:
        neighbor_id = to_memory_id
    elif to_memory_id == anchor_memory_id and relation_type in _REVERSIBLE_ASSOCIATION_TYPES:
        neighbor_id = from_memory_id
    else:
        return None
    if neighbor_id == anchor_memory_id:
        return None
    return {
        "memory_id": neighbor_id,
        "relation_type": relation_type,
        "strength": strength,
        "expansion_type": "association",
    }
