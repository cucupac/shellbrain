"""This module defines boot-time helpers for retrieval repository wiring."""


def get_retrieval_defaults() -> dict[str, float]:
    """This function returns baseline retrieval defaults used by boot wiring."""

    return {"semantic_weight": 1.0, "keyword_weight": 1.0, "k_rrf": 20.0}
