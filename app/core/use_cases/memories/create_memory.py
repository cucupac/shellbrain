"""This module defines the create-shellbrain use-case orchestration entry point."""

from uuid import uuid4

from app.core.contracts.requests import MemoryCreateRequest
from app.core.contracts.responses import OperationResult
from app.core.contracts.planned_effects import CreatePlanIds
from app.core.interfaces.embeddings import IEmbeddingProvider
from app.core.interfaces.idgen import IIdGenerator
from app.core.interfaces.unit_of_work import IUnitOfWork
from app.core.policies.memory_create_policy.plan import build_create_plan
from app.core.use_cases.plan_execution import apply_side_effects


class _UuidIdGenerator(IIdGenerator):
    """Default ID generator for direct use-case calls."""

    def new_id(self) -> str:
        return str(uuid4())


def execute_create_memory(
    request: MemoryCreateRequest,
    uow: IUnitOfWork,
    *,
    embedding_provider: IEmbeddingProvider,
    embedding_model: str,
    id_generator: IIdGenerator | None = None,
) -> OperationResult:
    """This function orchestrates create flow for an already-validated request."""

    id_generator = id_generator or _UuidIdGenerator()
    associations = request.memory.links.associations
    plan_ids = CreatePlanIds(
        memory_id=id_generator.new_id(),
        association_edge_ids=tuple(id_generator.new_id() for _ in associations),
        association_observation_ids=tuple(id_generator.new_id() for _ in associations),
    )
    payload = request.model_dump(mode="python")
    plan = build_create_plan(payload, plan_ids=plan_ids, embedding_model=embedding_model)
    apply_side_effects(plan, uow, embedding_provider=embedding_provider)
    return OperationResult(status="ok", data={"memory_id": plan_ids.memory_id, "planned_side_effects": plan})
