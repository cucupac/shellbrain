"""This module defines the update-shellbrain use-case orchestration entry point."""

from app.core.contracts.errors import DomainValidationError
from app.core.contracts.planned_effects import UpdatePlanIds
from app.core.contracts.memories import MemoryBatchUpdateRequest, MemoryUpdateRequest
from app.core.contracts.responses import UseCaseResult
from app.core.entities.settings import UpdatePolicySettings
from app.core.ports.runtime.idgen import IIdGenerator
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.policies.memories.update_plan import build_update_plan
from app.core.use_cases.memories.reference_checks import validate_update_request
from app.core.use_cases.plan_execution import apply_side_effects


def execute_update_memory(
    request: MemoryUpdateRequest | MemoryBatchUpdateRequest,
    uow: IUnitOfWork,
    *,
    id_generator: IIdGenerator,
    policy_settings: UpdatePolicySettings | None = None,
) -> UseCaseResult:
    """Orchestrate memory update validation, planning, and side-effect execution."""

    policy_settings = policy_settings or UpdatePolicySettings(
        gates=("schema", "semantic", "integrity")
    )
    validation_errors = validate_update_request(
        request, uow=uow, gates=policy_settings.gates
    )
    if validation_errors:
        raise DomainValidationError(validation_errors)
    if isinstance(request, MemoryBatchUpdateRequest):
        plan: list[dict[str, object]] = []
        updated_memory_ids: list[str] = []
        for item in request.updates:
            item_payload = {
                "repo_id": request.repo_id,
                "memory_id": item.memory_id,
                "update": item.update.model_dump(mode="python"),
            }
            plan.extend(
                build_update_plan(
                    item_payload,
                    plan_ids=_build_update_plan_ids(
                        item_payload["update"], id_generator=id_generator
                    ),
                )
            )
            updated_memory_ids.append(item.memory_id)
        apply_side_effects(plan, uow)
        problem_id = request.updates[0].update.problem_id
        return UseCaseResult(
            data={
                "problem_id": problem_id,
                "updated_memory_ids": updated_memory_ids,
                "applied_count": len(request.updates),
                "planned_side_effects": plan,
            },
        )

    payload = request.model_dump(mode="python")
    plan = build_update_plan(
        payload,
        plan_ids=_build_update_plan_ids(payload["update"], id_generator=id_generator),
    )
    apply_side_effects(plan, uow)
    return UseCaseResult(
        data={"memory_id": request.memory_id, "planned_side_effects": plan}
    )


def _build_update_plan_ids(
    update: dict[str, object], *, id_generator: IIdGenerator
) -> UpdatePlanIds:
    """Preallocate IDs needed by one update side-effect plan."""

    update_type = update["type"]
    if update_type == "utility_vote":
        return UpdatePlanIds(utility_observation_id=id_generator.new_id())
    if update_type == "fact_update_link":
        return UpdatePlanIds(fact_update_id=id_generator.new_id())
    if update_type == "association_link":
        return UpdatePlanIds(
            association_edge_id=id_generator.new_id(),
            association_observation_id=id_generator.new_id(),
        )
    return UpdatePlanIds()
