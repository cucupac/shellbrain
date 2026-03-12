"""This module defines boot-time helpers for retrieval repository wiring."""

from app.boot.config import get_config_provider


def get_retrieval_defaults() -> dict[str, float]:
    """This function returns baseline retrieval defaults used by boot wiring."""

    read_policy = get_config_provider().get_read_policy()
    weights = read_policy.get("weights") or {}
    fusion = read_policy.get("fusion") or {}
    return {
        "semantic_weight": float(weights.get("semantic", 1.0)),
        "keyword_weight": float(weights.get("keyword", 1.0)),
        "k_rrf": float(fusion.get("k_rrf", 20.0)),
    }
