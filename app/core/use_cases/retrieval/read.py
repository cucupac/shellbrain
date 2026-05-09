"""This module defines the read-shellbrain use-case orchestration entry point."""

from app.core.contracts.retrieval import MemoryReadRequest
from app.core.contracts.responses import UseCaseResult
from app.core.entities.settings import (
    ReadPolicySettings,
    ThresholdSettings,
    default_read_policy_settings,
    default_threshold_settings,
)
from app.core.ports.unit_of_work import IUnitOfWork
from app.core.use_cases.retrieval.context_pack_pipeline import build_context_pack
from app.core.use_cases.retrieval.read_concepts import append_concepts_to_pack


def execute_read_memory(
    request: MemoryReadRequest,
    uow: IUnitOfWork,
    *,
    read_settings: ReadPolicySettings | None = None,
    threshold_settings: ThresholdSettings | None = None,
) -> UseCaseResult:
    """This function orchestrates read flow with retrieval and context-pack policy hooks."""

    read_settings = read_settings or default_read_policy_settings()
    threshold_settings = threshold_settings or default_threshold_settings()
    payload = request.model_dump(mode="python")
    context_pack = build_context_pack(
        payload,
        keyword_retrieval=uow.keyword_retrieval,
        memories=uow.memories,
        semantic_retrieval=uow.semantic_retrieval,
        read_policy=uow.read_policy,
        vector_search=uow.vector_search,
        read_settings=read_settings,
        threshold_settings=threshold_settings,
    )
    context_pack = append_concepts_to_pack(
        pack=context_pack,
        request=request,
        concepts=uow.concepts,
        memories=uow.memories,
    )
    return UseCaseResult(data={"pack": context_pack})
