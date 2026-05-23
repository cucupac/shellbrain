"""This module defines semantic and keyword seed retrieval stage helpers."""

from typing import Any, Sequence

from app.core.entities.settings import ThresholdSettings, default_threshold_settings
from app.core.entities.memories import MemoryLifecycleStatus
from app.core.ports.embeddings.retrieval import IVectorSearch
from app.core.ports.db.retrieval_repositories import (
    IKeywordRetrievalRepo,
    ISemanticRetrievalRepo,
)
from app.core.policies.retrieval.bm25 import (
    BM25Document,
    admit_scored_documents,
    score_documents,
)
from app.core.policies.retrieval.lexical_query import (
    LexicalQuery,
    build_lexical_query,
    normalize_lexical_text,
)


def retrieve_seeds(
    request_data: dict[str, Any],
    *,
    semantic_retrieval: ISemanticRetrievalRepo,
    keyword_retrieval: IKeywordRetrievalRepo,
    vector_search: IVectorSearch | None,
    query_vector: Sequence[float] | None = None,
    query_model: str | None = None,
    thresholds: ThresholdSettings | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """This function retrieves initial semantic and keyword candidate seeds."""

    repo_id = request_data["repo_id"]
    include_global = bool(request_data["include_global"])
    kinds = request_data.get("kinds")
    limit = int(request_data["limit"])
    query_text = request_data["query"]
    lexical_query = build_lexical_query(query_text)
    resolved_query_vector = list(query_vector) if query_vector is not None else []
    resolved_query_model = query_model
    if query_vector is None and vector_search is not None:
        resolved_query_vector = list(vector_search.embed_query(query_text))
        if not resolved_query_vector:
            raise ValueError("Query embedding provider returned an empty vector")
        resolved_query_model = vector_search.model_name
    thresholds = thresholds or default_threshold_settings()
    semantic = [
        candidate
        for candidate in semantic_retrieval.query_semantic(
            repo_id=repo_id,
            include_global=include_global,
            query_vector=resolved_query_vector,
            query_model=resolved_query_model,
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
                query_terms=lexical_query.terms,
                candidate_limit=_keyword_candidate_limit(limit),
            ),
            lexical_query=lexical_query,
            mode=request_data["mode"],
            limit=limit,
        )
        if float(candidate["score"]) >= thresholds.keyword_threshold
    ]
    return {"semantic": semantic, "keyword": keyword}


def _rank_keyword_candidates(
    corpus_rows: Sequence[dict[str, Any]],
    *,
    lexical_query: LexicalQuery,
    mode: str,
    limit: int,
) -> list[dict[str, object]]:
    """Rank visible lexical rows through pure read policy helpers."""

    if not lexical_query.terms:
        return []
    documents = [
        BM25Document(
            document_id=str(row["memory_id"]),
            terms=normalize_lexical_text(str(row["text"])).terms_for(lexical_query),
        )
        for row in corpus_rows
    ]
    scored_documents = score_documents(lexical_query.terms, documents)
    status_by_memory_id = {
        str(row["memory_id"]): _required_status(row) for row in corpus_rows
    }
    admitted = []
    for candidate in admit_scored_documents(scored_documents, mode=mode):
        status = MemoryLifecycleStatus(status_by_memory_id[str(candidate["memory_id"])])
        item = dict(candidate)
        item["score"] = float(item["score"]) * status.retrieval_multiplier
        if item["score"] > 0:
            admitted.append(item)
    admitted.sort(key=lambda item: (-float(item["score"]), str(item["memory_id"])))
    return admitted[:limit]


def _required_status(row: dict[str, Any]) -> str:
    """Return the required memory status for keyword retrieval rows."""

    if "status" not in row:
        raise ValueError(f"Keyword corpus row {row.get('memory_id')} is missing status")
    return str(row["status"])


def _keyword_candidate_limit(limit: int) -> int:
    """Return the bounded lexical candidate pool size used before pure BM25 ranking."""

    return max(limit * 25, 200)
