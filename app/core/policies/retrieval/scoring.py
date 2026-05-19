"""This module defines scoring helpers for explicit and implicit read candidates."""

from typing import Any


def score_candidates(
    candidates: dict[str, list[dict[str, Any]]], payload: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """This function computes base scores used for bucket ranking and spillover."""

    _ = payload
    return {
        "direct": _score_direct_candidates(candidates.get("direct", [])),
        "explicit": _score_explicit_candidates(candidates.get("explicit", [])),
        "implicit": _score_implicit_candidates(candidates.get("implicit", [])),
    }


def _score_direct_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign direct-bucket scores from reciprocal-rank fusion output."""

    scored = []
    for candidate in candidates:
        item = dict(candidate)
        item["score"] = _required_float(candidate, "rrf_score", "direct")
        scored.append(item)
    return _sort_scored_candidates(scored)


def _score_explicit_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Assign explicit-bucket scores from anchor relevance and explicit-link metadata."""

    scored = []
    for candidate in candidates:
        item = dict(candidate)
        anchor_score = _required_float(candidate, "anchor_score", "explicit")
        depth = _required_positive_int(candidate, "depth", "explicit")
        relation_strength = 1.0
        if candidate.get("expansion_type") == "association":
            relation_strength = _required_float(
                candidate, "relation_strength", "explicit association"
            )
        item["score"] = anchor_score * relation_strength / depth
        scored.append(item)
    return _sort_scored_candidates(scored)


def _score_implicit_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Assign implicit-bucket scores from anchor relevance, similarity, and hop count."""

    scored = []
    for candidate in candidates:
        item = dict(candidate)
        anchor_score = _required_float(candidate, "anchor_score", "implicit")
        hop = _required_positive_int(candidate, "hop", "implicit")
        neighbor_similarity = _required_float(
            candidate, "neighbor_similarity", "implicit"
        )
        item["score"] = anchor_score * neighbor_similarity / hop
        scored.append(item)
    return _sort_scored_candidates(scored)


def _sort_scored_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return candidates in deterministic descending score order."""

    return sorted(
        candidates, key=lambda item: (-float(item["score"]), str(item["memory_id"]))
    )


def _required_float(
    candidate: dict[str, Any], field: str, candidate_type: str
) -> float:
    """Return a required numeric candidate field or fail with context."""

    if field not in candidate:
        raise ValueError(
            f"{candidate_type} candidate {candidate.get('memory_id')} "
            f"is missing required {field}"
        )
    return float(candidate[field])


def _required_positive_int(
    candidate: dict[str, Any], field: str, candidate_type: str
) -> int:
    """Return a required positive integer candidate field or fail with context."""

    if field not in candidate:
        raise ValueError(
            f"{candidate_type} candidate {candidate.get('memory_id')} "
            f"is missing required {field}"
        )
    value = int(candidate[field])
    if value <= 0:
        raise ValueError(
            f"{candidate_type} candidate {candidate.get('memory_id')} "
            f"has invalid {field}: {value}"
        )
    return value
