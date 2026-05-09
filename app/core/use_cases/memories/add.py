"""This module defines the create-shellbrain use-case orchestration entry point."""

from app.core.contracts.errors import DomainValidationError
from app.core.contracts.requests import MemoryCreateRequest
from app.core.contracts.responses import UseCaseResult
from app.core.contracts.planned_effects import CreatePlanIds
from app.core.entities.settings import CreatePolicySettings
from app.core.ports.embeddings import IEmbeddingProvider
from app.core.ports.idgen import IIdGenerator
from app.core.ports.unit_of_work import IUnitOfWork
from app.core.policies.memories.add_plan import build_create_plan
from app.core.use_cases.plan_execution import apply_side_effects
from app.core.use_cases.memories.reference_checks import validate_create_request


def execute_create_memory(
    request: MemoryCreateRequest,
    uow: IUnitOfWork,
    *,
    embedding_provider: IEmbeddingProvider,
    embedding_model: str,
    id_generator: IIdGenerator,
    policy_settings: CreatePolicySettings | None = None,
) -> UseCaseResult:
    """Orchestrate memory create validation, planning, and side-effect execution."""

    policy_settings = policy_settings or CreatePolicySettings(
        gates=("schema", "semantic", "integrity"), defaults={"scope": "repo"}
    )
    validation_errors = validate_create_request(
        request, uow=uow, gates=policy_settings.gates
    )
    if validation_errors:
        raise DomainValidationError(validation_errors)
    associations = request.memory.links.associations
    plan_ids = CreatePlanIds(
        memory_id=id_generator.new_id(),
        association_edge_ids=tuple(id_generator.new_id() for _ in associations),
        association_observation_ids=tuple(id_generator.new_id() for _ in associations),
    )
    payload = request.model_dump(mode="python")
    plan = build_create_plan(
        payload, plan_ids=plan_ids, embedding_model=embedding_model
    )
    apply_side_effects(plan, uow, embedding_provider=embedding_provider)
    return UseCaseResult(
        data={"memory_id": plan_ids.memory_id, "planned_side_effects": plan}
    )
