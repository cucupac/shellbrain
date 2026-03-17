"""This module defines the read-shellbrain use-case orchestration entry point."""

from shellbrain.core.contracts.requests import MemoryReadRequest
from shellbrain.core.contracts.responses import OperationResult
from shellbrain.core.interfaces.unit_of_work import IUnitOfWork
from shellbrain.core.policies.read_policy.pipeline import build_context_pack


def execute_read_memory(request: MemoryReadRequest, uow: IUnitOfWork) -> OperationResult:
    """This function orchestrates read flow with retrieval and context-pack policy hooks."""

    payload = request.model_dump(mode="python")
    context_pack = build_context_pack(
        payload,
        keyword_retrieval=uow.keyword_retrieval,
        memories=uow.memories,
        semantic_retrieval=uow.semantic_retrieval,
        read_policy=uow.read_policy,
        vector_search=uow.vector_search,
    )
    return OperationResult(status="ok", data={"pack": context_pack})
