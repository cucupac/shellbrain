"""Helpers for constructing normalized lexical queries and document terms."""

from __future__ import annotations

import re
from dataclasses import dataclass


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "before",
        "by",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "these",
        "this",
        "those",
        "to",
        "with",
        "without",
    }
)


@dataclass(frozen=True, slots=True)
class LexicalQuery:
    """Normalized lexical query terms used by the keyword retrieval lane."""

    raw_terms: tuple[str, ...]
    informative_terms: tuple[str, ...]
    terms: tuple[str, ...]
    uses_stopword_fallback: bool


@dataclass(frozen=True, slots=True)
class NormalizedLexicalText:
    """Normalized raw and informative token views for one text payload."""

    raw_terms: tuple[str, ...]
    informative_terms: tuple[str, ...]

    def terms_for(self, query: LexicalQuery) -> tuple[str, ...]:
        """Return the document term view aligned to the lexical query mode."""

        if query.uses_stopword_fallback:
            return self.raw_terms
        return self.informative_terms


def build_lexical_query(query_text: str) -> LexicalQuery:
    """Build a normalized lexical query with strict informative-term semantics."""

    normalized = normalize_lexical_text(query_text)
    raw_terms = _unique_terms(normalized.raw_terms)
    informative_terms = _unique_terms(normalized.informative_terms)
    uses_stopword_fallback = not informative_terms and bool(raw_terms)
    terms = raw_terms if uses_stopword_fallback else informative_terms
    return LexicalQuery(
        raw_terms=raw_terms,
        informative_terms=informative_terms,
        terms=terms,
        uses_stopword_fallback=uses_stopword_fallback,
    )


def normalize_lexical_text(text: str) -> NormalizedLexicalText:
    """Normalize text into raw and informative lexical token sequences."""

    raw_terms = tuple(_TOKEN_PATTERN.findall(text.lower()))
    informative_terms = tuple(term for term in raw_terms if term not in _STOPWORDS)
    return NormalizedLexicalText(raw_terms=raw_terms, informative_terms=informative_terms)


def _unique_terms(terms: tuple[str, ...]) -> tuple[str, ...]:
    """Deduplicate terms while preserving original order."""

    seen: set[str] = set()
    ordered: list[str] = []
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        ordered.append(term)
    return tuple(ordered)
