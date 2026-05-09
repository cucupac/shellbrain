"""Helpers for scoring lexical candidates with Okapi BM25 and coverage-aware admission."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log
from typing import Literal, Sequence


_K1 = 1.2
_B = 0.75
_COVERAGE_THRESHOLD_BY_MODE = {
    "targeted": 0.65,
    "ambient": 0.80,
}


@dataclass(frozen=True, slots=True)
class BM25Document:
    """Normalized document representation used for BM25 scoring."""

    memory_id: str
    terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BM25ScoredDocument:
    """Scored lexical candidate with query-coverage metadata."""

    memory_id: str
    score: float
    coverage: float


def score_documents(
    query_terms: Sequence[str],
    documents: Sequence[BM25Document],
    *,
    k1: float = _K1,
    b: float = _B,
) -> list[BM25ScoredDocument]:
    """Return BM25 scores and weighted query coverage for partially matching documents."""

    normalized_query_terms = tuple(query_terms)
    if not normalized_query_terms or not documents:
        return []

    term_frequencies = {
        document.memory_id: Counter(document.terms) for document in documents
    }
    corpus_size = len(documents)
    average_length = sum(len(document.terms) for document in documents) / corpus_size
    if average_length <= 0.0:
        return []

    inverse_document_frequencies = {
        term: _inverse_document_frequency(
            sum(
                1
                for document in documents
                if term in term_frequencies[document.memory_id]
            ),
            corpus_size,
        )
        for term in normalized_query_terms
    }
    total_query_weight = sum(inverse_document_frequencies.values())
    if total_query_weight <= 0.0:
        return []

    scored: list[BM25ScoredDocument] = []
    for document in documents:
        frequencies = term_frequencies[document.memory_id]
        matched_terms = tuple(
            term for term in normalized_query_terms if term in frequencies
        )
        if not matched_terms:
            continue

        score = 0.0
        matched_query_weight = 0.0
        document_length = len(document.terms)
        normalization = k1 * (1 - b + b * document_length / average_length)
        for term in matched_terms:
            inverse_document_frequency = inverse_document_frequencies[term]
            term_frequency = frequencies[term]
            score += inverse_document_frequency * (
                (term_frequency * (k1 + 1)) / (term_frequency + normalization)
            )
            matched_query_weight += inverse_document_frequency

        if score > 0.0:
            scored.append(
                BM25ScoredDocument(
                    memory_id=document.memory_id,
                    score=score,
                    coverage=matched_query_weight / total_query_weight,
                )
            )

    return sorted(scored, key=lambda item: (-item.score, item.memory_id))


def admit_scored_documents(
    scored_documents: Sequence[BM25ScoredDocument],
    *,
    mode: Literal["ambient", "targeted"],
) -> list[dict[str, object]]:
    """Apply the mode-aware weighted query-coverage gate to scored lexical candidates."""

    threshold = _COVERAGE_THRESHOLD_BY_MODE[mode]
    admitted = [
        {"memory_id": document.memory_id, "score": document.score}
        for document in scored_documents
        if document.coverage >= threshold
    ]
    return sorted(
        admitted, key=lambda item: (-float(item["score"]), str(item["memory_id"]))
    )


def _inverse_document_frequency(document_frequency: int, corpus_size: int) -> float:
    """Return the BM25 IDF weight for one query term in the current visible corpus."""

    return log(
        1 + (corpus_size - document_frequency + 0.5) / (document_frequency + 0.5)
    )
