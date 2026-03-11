"""This module defines reciprocal-rank fusion helpers for direct seed ranking."""

from typing import Any

from app.boot.retrieval import get_retrieval_defaults


def fuse_with_rrf(semantic: list[dict[str, Any]], keyword: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """This function merges lane candidates using reciprocal-rank fusion."""

    defaults = get_retrieval_defaults()
    k_rrf = defaults["k_rrf"]
    lane_weights = {
        "semantic": defaults["semantic_weight"],
        "keyword": defaults["keyword_weight"],
    }
    fused: dict[str, dict[str, Any]] = {}

    for lane_name, candidates in (("semantic", semantic), ("keyword", keyword)):
        for rank, candidate in enumerate(candidates, start=1):
            memory_id = candidate["memory_id"]
            entry = fused.setdefault(
                memory_id,
                {
                    "memory_id": memory_id,
                    "rrf_score": 0.0,
                    "rank_semantic": None,
                    "rank_keyword": None,
                },
            )
            entry[f"rank_{lane_name}"] = rank
            entry["rrf_score"] += lane_weights[lane_name] / (k_rrf + rank)

    return sorted(fused.values(), key=lambda item: (-float(item["rrf_score"]), str(item["memory_id"])))
