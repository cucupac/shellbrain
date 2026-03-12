"""This module defines semantic and keyword seed retrieval stage helpers."""

from typing import Any

from app.core.interfaces.repos import IKeywordRetrievalRepo, ISemanticRetrievalRepo
from app.core.interfaces.retrieval import IVectorSearch


def retrieve_seeds(
    payload: dict[str, Any],
    *,
    semantic_retrieval: ISemanticRetrievalRepo,
    keyword_retrieval: IKeywordRetrievalRepo,
    vector_search: IVectorSearch | None,
) -> dict[str, list[dict[str, Any]]]:
    """This function retrieves initial semantic and keyword candidate seeds."""

    repo_id = payload["repo_id"]
    include_global = payload.get("include_global", True)
    kinds = payload.get("kinds")
    limit = int(payload.get("limit", 20))
    query_text = payload["query"]
    query_vector = (
        list(vector_search.embed_query(query_text))
        if vector_search is not None
        else []
    )

    semantic = list(
        semantic_retrieval.query_semantic(
            repo_id=repo_id,
            include_global=include_global,
            query_vector=query_vector,
            kinds=kinds,
            limit=limit,
        )
    )
    keyword = list(
        keyword_retrieval.query_keyword(
            repo_id=repo_id,
            mode=payload["mode"],
            include_global=include_global,
            query_text=query_text,
            kinds=kinds,
            limit=limit,
        )
    )
    return {"semantic": semantic, "keyword": keyword}
