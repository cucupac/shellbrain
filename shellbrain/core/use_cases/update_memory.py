"""This module defines the update-shellbrain use-case orchestration entry point."""

from shellbrain.core.contracts.requests import MemoryBatchUpdateRequest, MemoryUpdateRequest
from shellbrain.core.contracts.responses import OperationResult
from shellbrain.core.interfaces.unit_of_work import IUnitOfWork
from shellbrain.core.policies.update_policy.pipeline import apply_update_plan, build_update_plan


def execute_update_memory(request: MemoryUpdateRequest | MemoryBatchUpdateRequest, uow: IUnitOfWork) -> OperationResult:
    """This function orchestrates update flow for an already-validated request."""

    if isinstance(request, MemoryBatchUpdateRequest):
        plan: list[dict[str, object]] = []
        updated_memory_ids: list[str] = []
        for item in request.updates:
            plan.extend(
                build_update_plan(
                    {
                        "repo_id": request.repo_id,
                        "memory_id": item.memory_id,
                        "update": item.update.model_dump(mode="python"),
                    }
                )
            )
            updated_memory_ids.append(item.memory_id)
        apply_update_plan(plan, uow)
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

    plan = build_update_plan(request.model_dump(mode="python"))
    apply_update_plan(plan, uow)
    return OperationResult(status="ok", data={"memory_id": request.memory_id, "planned_side_effects": plan})
