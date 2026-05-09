"""Pure concept text search ranking."""

from __future__ import annotations

from typing import Any, Sequence


_FIELD_WEIGHTS = {
    "alias": 4.0,
    "slug": 3.0,
    "name": 3.0,
    "claim": 2.0,
}
_FIELD_REASONS = {
    "alias": "query_alias",
    "slug": "query_slug",
    "name": "query_name",
    "claim": "query_claim",
}


def rank_concept_search_rows(
    rows: Sequence[dict[str, Any]],
    *,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Return deterministic concept matches for query text."""

    normalized_query = normalize_concept_search_text(query)
    if not normalized_query:
        return []
    matches: dict[str, dict[str, Any]] = {}
    for row in rows:
        field = str(row["field"])
        weight = _FIELD_WEIGHTS.get(field)
        reason = _FIELD_REASONS.get(field)
        if weight is None or reason is None:
            continue
        _maybe_add_text_match(
            matches,
            concept_id=str(row["concept_id"]),
            normalized_query=normalized_query,
            normalized_value=normalize_concept_search_text(str(row["text"])),
            display_value=str(row["display"]),
            reason=reason,
            score=weight,
        )
    ranked = sorted(
        matches.values(),
        key=lambda item: (-float(item["score"]), str(item["concept_id"])),
    )
    return ranked[:limit]


def normalize_concept_search_text(value: str) -> str:
    """Normalize natural text for query matching."""

    return " ".join(value.strip().lower().split())


def _maybe_add_text_match(
    matches: dict[str, dict[str, Any]],
    *,
    concept_id: str,
    normalized_query: str,
    normalized_value: str,
    display_value: str,
    reason: str,
    score: float,
) -> None:
    """Record a query match when query text overlaps a concept field."""

    if not normalized_value:
        return
    terms = [term for term in normalized_query.split() if len(term) >= 3]
    matches_exact_phrase = (
        normalized_value in normalized_query or normalized_query in normalized_value
    )
    matches_terms = bool(terms) and all(term in normalized_value for term in terms[:4])
    if not matches_exact_phrase and not matches_terms:
        return
    existing = matches.get(concept_id)
    if existing is None or score > float(existing["score"]):
        matches[concept_id] = {
            "concept_id": concept_id,
            "reason": reason,
            "matched": display_value,
            "score": score,
        }
