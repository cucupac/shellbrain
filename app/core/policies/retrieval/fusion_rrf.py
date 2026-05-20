"""This module defines reciprocal-rank fusion helpers for direct seed ranking."""

from typing import Any, Mapping

from app.core.entities.settings import default_read_policy_settings


def fuse_with_rrf(
    semantic: list[dict[str, Any]],
    keyword: list[dict[str, Any]],
    *,
    retrieval_defaults: Mapping[str, float] | None = None,
    id_key: str = "memory_id",
) -> list[dict[str, Any]]:
    """This function merges lane candidates using reciprocal-rank fusion."""

    retrieval_defaults = (
        retrieval_defaults or default_read_policy_settings().retrieval_defaults()
    )
    k_rrf = float(retrieval_defaults["k_rrf"])
    lane_weights = {
        "semantic": float(retrieval_defaults["semantic_weight"]),
        "keyword": float(retrieval_defaults["keyword_weight"]),
    }
    fused: dict[str, dict[str, Any]] = {}

    for lane_name, candidates in (("semantic", semantic), ("keyword", keyword)):
        for rank, candidate in enumerate(candidates, start=1):
            item_id = candidate[id_key]
            entry = fused.setdefault(
                item_id,
                {
                    id_key: item_id,
                    "rrf_score": 0.0,
                    "rank_semantic": None,
                    "rank_keyword": None,
                },
            )
            entry[f"rank_{lane_name}"] = rank
            entry["rrf_score"] += lane_weights[lane_name] / (k_rrf + rank)

    return sorted(
        fused.values(),
        key=lambda item: (-float(item["rrf_score"]), str(item[id_key])),
    )
