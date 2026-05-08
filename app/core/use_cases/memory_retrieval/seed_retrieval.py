"""This module defines semantic and keyword seed retrieval stage helpers."""

from typing import Any, Sequence

from app.core.entities.settings import ThresholdSettings, default_threshold_settings
from app.core.interfaces.repos import IKeywordRetrievalRepo, ISemanticRetrievalRepo
from app.core.interfaces.retrieval import IVectorSearch
from app.core.policies.memory_read_policy.bm25 import BM25Document, admit_scored_documents, score_documents
from app.core.policies.memory_read_policy.lexical_query import build_lexical_query, normalize_lexical_text


def retrieve_seeds(
    request_data: dict[str, Any],
    *,
    semantic_retrieval: ISemanticRetrievalRepo,
    keyword_retrieval: IKeywordRetrievalRepo,
    vector_search: IVectorSearch | None,
    thresholds: ThresholdSettings | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """This function retrieves initial semantic and keyword candidate seeds."""

    repo_id = request_data["repo_id"]
    include_global = bool(request_data["include_global"])
    kinds = request_data.get("kinds")
    limit = int(request_data["limit"])
    query_text = request_data["query"]
    query_vector = (
        list(vector_search.embed_query(query_text))
        if vector_search is not None
        else []
    )
    thresholds = thresholds or _coerce_threshold_settings(get_threshold_settings())
    semantic = [
        candidate
        for candidate in semantic_retrieval.query_semantic(
            repo_id=repo_id,
            include_global=include_global,
            query_vector=query_vector,
            kinds=kinds,
            limit=limit,
        )
        if float(candidate["score"]) >= thresholds.semantic_threshold
    ]
    keyword = [
        candidate
        for candidate in _rank_keyword_candidates(
            keyword_retrieval.list_keyword_corpus(
                repo_id=repo_id,
                include_global=include_global,
                kinds=kinds,
            ),
            query_text=query_text,
            mode=request_data["mode"],
            limit=limit,
        )
        if float(candidate["score"]) >= thresholds.keyword_threshold
    ]
    return {"semantic": semantic, "keyword": keyword}


def _rank_keyword_candidates(
    corpus_rows: Sequence[dict[str, Any]],
    *,
    query_text: str,
    mode: str,
    limit: int,
) -> list[dict[str, object]]:
    """Rank visible lexical rows through pure read policy helpers."""

    lexical_query = build_lexical_query(query_text)
    if not lexical_query.terms:
        return []
    documents = [
        BM25Document(
            memory_id=str(row["memory_id"]),
            terms=normalize_lexical_text(str(row["text"])).terms_for(lexical_query),
        )
        for row in corpus_rows
    ]
    scored_documents = score_documents(lexical_query.terms, documents)
    return admit_scored_documents(scored_documents, mode=mode)[:limit]


def get_threshold_settings() -> dict[str, float]:
    """Compatibility seam for direct retrieval-stage tests."""

    return default_threshold_settings().to_dict()


def _coerce_threshold_settings(settings: ThresholdSettings | dict[str, float]) -> ThresholdSettings:
    if isinstance(settings, ThresholdSettings):
        return settings
    return ThresholdSettings(
        semantic_threshold=float(settings["semantic_threshold"]),
        keyword_threshold=float(settings["keyword_threshold"]),
    )
