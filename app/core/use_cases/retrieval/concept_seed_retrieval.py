"""Concept keyword and semantic candidate retrieval helpers."""

from __future__ import annotations

from typing import Any, Sequence

from app.core.entities.settings import ThresholdSettings, default_threshold_settings
from app.core.policies.retrieval.bm25 import (
    BM25Document,
    admit_scored_documents,
    score_documents,
)
from app.core.policies.retrieval.fusion_rrf import fuse_with_rrf
from app.core.policies.retrieval.lexical_query import (
    LexicalQuery,
    build_lexical_query,
    normalize_lexical_text,
)
from app.core.ports.db.retrieval_repositories import (
    IConceptKeywordRetrievalRepo,
    IConceptSemanticRetrievalRepo,
)


def retrieve_concept_seeds(
    request_data: dict[str, Any],
    *,
    concept_keyword_retrieval: IConceptKeywordRetrievalRepo | None,
    concept_semantic_retrieval: IConceptSemanticRetrievalRepo | None,
    query_vector: Sequence[float],
    query_model: str | None,
    thresholds: ThresholdSettings | None = None,
    limit: int = 20,
) -> dict[str, list[dict[str, Any]]]:
    """Retrieve concept candidates from semantic and keyword concept lanes."""

    lexical_query = build_lexical_query(str(request_data["query"]))
    thresholds = thresholds or default_threshold_settings()
    semantic = _semantic_concept_candidates(
        request_data,
        concept_semantic_retrieval=concept_semantic_retrieval,
        query_vector=query_vector,
        query_model=query_model,
        thresholds=thresholds,
        limit=limit,
    )
    keyword = _keyword_concept_candidates(
        request_data,
        concept_keyword_retrieval=concept_keyword_retrieval,
        lexical_query=lexical_query,
        thresholds=thresholds,
        limit=limit,
    )
    fused = fuse_with_rrf(semantic, keyword, id_key="concept_id")
    return {"semantic": semantic, "keyword": keyword, "fused": fused}


def _semantic_concept_candidates(
    request_data: dict[str, Any],
    *,
    concept_semantic_retrieval: IConceptSemanticRetrievalRepo | None,
    query_vector: Sequence[float],
    query_model: str | None,
    thresholds: ThresholdSettings,
    limit: int,
) -> list[dict[str, Any]]:
    if concept_semantic_retrieval is None or not query_vector:
        return []
    return [
        candidate
        for candidate in concept_semantic_retrieval.query_concepts_semantic(
            repo_id=str(request_data["repo_id"]),
            query_vector=query_vector,
            query_model=query_model,
            limit=limit,
        )
        if float(candidate["score"]) >= thresholds.semantic_threshold
    ]


def _keyword_concept_candidates(
    request_data: dict[str, Any],
    *,
    concept_keyword_retrieval: IConceptKeywordRetrievalRepo | None,
    lexical_query: LexicalQuery,
    thresholds: ThresholdSettings,
    limit: int,
) -> list[dict[str, Any]]:
    if concept_keyword_retrieval is None:
        return []
    candidates = _rank_concept_keyword_candidates(
        concept_keyword_retrieval.list_concept_keyword_corpus(
            repo_id=str(request_data["repo_id"]),
            query_terms=lexical_query.terms,
            candidate_limit=_concept_keyword_candidate_limit(limit),
        ),
        lexical_query=lexical_query,
        mode=str(request_data["mode"]),
        limit=limit,
    )
    return [
        candidate
        for candidate in candidates
        if float(candidate["score"]) >= thresholds.keyword_threshold
    ]


def _rank_concept_keyword_candidates(
    corpus_rows: Sequence[dict[str, Any]],
    *,
    lexical_query: LexicalQuery,
    mode: str,
    limit: int,
) -> list[dict[str, object]]:
    """Rank active concept rows through pure BM25 helpers."""

    if not lexical_query.terms:
        return []
    documents = [
        BM25Document(
            document_id=str(row["concept_id"]),
            terms=normalize_lexical_text(str(row["text"])).terms_for(lexical_query),
        )
        for row in corpus_rows
    ]
    scored_documents = score_documents(lexical_query.terms, documents)
    return admit_scored_documents(
        scored_documents,
        mode=mode,
        output_id_key="concept_id",
        coverage_threshold=0.25,
    )[:limit]


def _concept_keyword_candidate_limit(limit: int) -> int:
    return max(limit * 10, 100)
