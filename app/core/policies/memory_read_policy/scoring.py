"""This module defines scoring helpers for explicit and implicit read candidates."""

from typing import Any


def score_candidates(candidates: dict[str, list[dict[str, Any]]], payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
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
        item["score"] = float(candidate.get("rrf_score", candidate.get("score", 0.0)))
        scored.append(item)
    return _sort_scored_candidates(scored)


def _score_explicit_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign explicit-bucket scores from anchor relevance and explicit-link metadata."""

    scored = []
    for candidate in candidates:
        item = dict(candidate)
        anchor_score = float(candidate.get("anchor_score", candidate.get("score", 0.0)))
        depth = max(1, int(candidate.get("depth", 1)))
        relation_strength = 1.0
        if candidate.get("expansion_type") == "association":
            relation_strength = float(candidate.get("relation_strength", 1.0))
        item["score"] = anchor_score * relation_strength / depth
        scored.append(item)
    return _sort_scored_candidates(scored)


def _score_implicit_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign implicit-bucket scores from anchor relevance, similarity, and hop count."""

    scored = []
    for candidate in candidates:
        item = dict(candidate)
        anchor_score = float(candidate.get("anchor_score", candidate.get("score", 0.0)))
        hop = max(1, int(candidate.get("hop", 1)))
        neighbor_similarity = float(candidate.get("neighbor_similarity", 1.0))
        item["score"] = anchor_score * neighbor_similarity / hop
        scored.append(item)
    return _sort_scored_candidates(scored)


def _sort_scored_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return candidates in deterministic descending score order."""

    return sorted(candidates, key=lambda item: (-float(item["score"]), str(item["memory_id"])))
