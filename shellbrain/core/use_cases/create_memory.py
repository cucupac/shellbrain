"""This module defines the create-shellbrain use-case orchestration entry point."""

from uuid import uuid4

from shellbrain.core.contracts.requests import MemoryCreateRequest
from shellbrain.core.contracts.responses import OperationResult
from shellbrain.core.interfaces.embeddings import IEmbeddingProvider
from shellbrain.core.interfaces.unit_of_work import IUnitOfWork
from shellbrain.core.policies.create_policy.pipeline import apply_create_plan, build_create_plan


def execute_create_memory(
    request: MemoryCreateRequest,
    uow: IUnitOfWork,
    *,
    embedding_provider: IEmbeddingProvider,
    embedding_model: str,
) -> OperationResult:
    """This function orchestrates create flow for an already-validated request."""

    memory_id = str(uuid4())
    payload = request.model_dump(mode="python")
    payload["memory_id"] = memory_id
    plan = build_create_plan(payload, embedding_model=embedding_model)
    apply_create_plan(plan, uow, embedding_provider=embedding_provider)
    return OperationResult(status="ok", data={"memory_id": memory_id, "planned_side_effects": plan})
