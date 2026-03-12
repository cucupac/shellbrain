"""This module defines the update-memory use-case orchestration entry point."""

from app.core.contracts.requests import MemoryUpdateRequest
from app.core.contracts.responses import OperationResult
from app.core.interfaces.unit_of_work import IUnitOfWork
from app.core.policies.update_policy.pipeline import apply_update_plan, build_update_plan


def execute_update_memory(request: MemoryUpdateRequest, uow: IUnitOfWork) -> OperationResult:
    """This function orchestrates update flow for an already-validated request."""

    plan = build_update_plan(request.model_dump(mode="python"))
    apply_update_plan(plan, uow)
    return OperationResult(status="ok", data={"memory_id": request.memory_id, "planned_side_effects": plan})
