"""This module defines semantic and keyword seed retrieval stage helpers."""

from typing import Any

from app.core.interfaces.repos import IKeywordRetrievalRepo, ISemanticRetrievalRepo


def retrieve_seeds(
    payload: dict[str, Any],
    *,
    semantic_retrieval: ISemanticRetrievalRepo,
    keyword_retrieval: IKeywordRetrievalRepo,
) -> dict[str, list[dict[str, Any]]]:
    """This function retrieves initial semantic and keyword candidate seeds."""

    repo_id = payload["repo_id"]
    include_global = payload.get("include_global", True)
    kinds = payload.get("kinds")
    limit = payload.get("limit", 20)
    query_text = payload["query"]

    semantic = list(
        semantic_retrieval.query_semantic(
            repo_id=repo_id,
            include_global=include_global,
            query_vector=[],
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
