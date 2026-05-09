"""Shared helper builders for update execution tests."""

from collections.abc import Callable

from app.core.contracts.memories import MemoryUpdateRequest


def make_update_request(
    *,
    repo_id: str,
    memory_id: str,
    update: dict[str, object],
) -> MemoryUpdateRequest:
    """Build a valid update request with caller-provided payload."""

    return MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": repo_id,
            "memory_id": memory_id,
            "update": update,
        }
    )


def snapshot_related_update_counts(count_rows: Callable[[str], int]) -> dict[str, int]:
    """Capture counts for the related-record tables written by non-archive updates."""

    return {
        "utility_observations": count_rows("utility_observations"),
        "fact_updates": count_rows("fact_updates"),
        "association_edges": count_rows("association_edges"),
        "association_observations": count_rows("association_observations"),
        "association_edge_evidence": count_rows("association_edge_evidence"),
        "evidence_refs": count_rows("evidence_refs"),
    }
