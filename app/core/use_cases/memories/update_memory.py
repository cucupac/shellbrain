"""This module defines the update-shellbrain use-case orchestration entry point."""

from uuid import uuid4

from app.core.contracts.planned_effects import UpdatePlanIds
from app.core.contracts.requests import MemoryBatchUpdateRequest, MemoryUpdateRequest
from app.core.contracts.responses import OperationResult
from app.core.interfaces.idgen import IIdGenerator
from app.core.interfaces.unit_of_work import IUnitOfWork
from app.core.policies.memory_update_policy.plan import build_update_plan
from app.core.use_cases.plan_execution import apply_side_effects


class _UuidIdGenerator(IIdGenerator):
    """Default ID generator for direct use-case calls."""

    def new_id(self) -> str:
        return str(uuid4())


def execute_update_memory(
    request: MemoryUpdateRequest | MemoryBatchUpdateRequest,
    uow: IUnitOfWork,
    *,
    id_generator: IIdGenerator | None = None,
) -> OperationResult:
    """This function orchestrates update flow for an already-validated request."""

    id_generator = id_generator or _UuidIdGenerator()
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
                    plan_ids=_build_update_plan_ids(item_payload["update"], id_generator=id_generator),
                )
            )
            updated_memory_ids.append(item.memory_id)
        apply_side_effects(plan, uow)
        problem_id = request.updates[0].update.problem_id
        return OperationResult(
            status="ok",
            data={
                "problem_id": problem_id,
                "updated_memory_ids": updated_memory_ids,
                "applied_count": len(request.updates),
                "planned_side_effects": plan,
            },
        )

    payload = request.model_dump(mode="python")
    plan = build_update_plan(payload, plan_ids=_build_update_plan_ids(payload["update"], id_generator=id_generator))
    apply_side_effects(plan, uow)
    return OperationResult(status="ok", data={"memory_id": request.memory_id, "planned_side_effects": plan})


def _build_update_plan_ids(update: dict[str, object], *, id_generator: IIdGenerator) -> UpdatePlanIds:
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
