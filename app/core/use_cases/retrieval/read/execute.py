"""This module defines the read-shellbrain use-case orchestration entry point."""

from typing import Any

from app.core.entities.settings import (
    ReadPolicySettings,
    ThresholdSettings,
    default_read_policy_settings,
    default_threshold_settings,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.use_cases.retrieval.read_concepts import append_concepts_to_pack
from app.core.use_cases.retrieval.read.request import MemoryReadRequest
from app.core.use_cases.retrieval.read.result import ReadMemoryResult


def execute_read_memory(
    request: MemoryReadRequest,
    uow: IUnitOfWork,
    *,
    read_settings: ReadPolicySettings | None = None,
    threshold_settings: ThresholdSettings | None = None,
) -> ReadMemoryResult:
    """This function orchestrates read flow with retrieval and context-pack policy hooks."""

    read_settings = read_settings or default_read_policy_settings()
    threshold_settings = threshold_settings or default_threshold_settings()
    payload = request.model_dump(mode="python")
    query_vector, query_model = _resolve_query_embedding(
        query=payload["query"], vector_search=uow.vector_search
    )
    context_pack = _build_context_pack(
        payload,
        keyword_retrieval=uow.keyword_retrieval,
        memories=uow.memories,
        semantic_retrieval=uow.semantic_retrieval,
        read_policy=uow.read_policy,
        vector_search=uow.vector_search,
        read_settings=read_settings,
        threshold_settings=threshold_settings,
        query_vector=query_vector,
        query_model=query_model,
    )
    context_pack = append_concepts_to_pack(
        pack=context_pack,
        request=request,
        concepts=uow.concepts,
        memories=uow.memories,
        concept_keyword_retrieval=uow.concept_keyword_retrieval,
        concept_semantic_retrieval=uow.concept_semantic_retrieval,
        query_vector=query_vector,
        query_model=query_model,
        threshold_settings=threshold_settings,
    )
    return ReadMemoryResult(pack=context_pack)


def _build_context_pack(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Resolve the public package hook so tests and adapters can monkeypatch it."""

    from app.core.use_cases.retrieval import read as read_package

    return read_package.build_context_pack(*args, **kwargs)


def _resolve_query_embedding(*, query: str, vector_search) -> tuple[list[float], str | None]:
    """Return one read-path query vector so memory and concept retrieval share it."""

    if vector_search is None:
        return [], None
    query_vector = list(vector_search.embed_query(query))
    if not query_vector:
        raise ValueError("Query embedding provider returned an empty vector")
    return query_vector, vector_search.model_name
