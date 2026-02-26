"""This module defines the update-memory use-case orchestration entry point."""

from app.core.contracts.requests import MemoryUpdateRequest
from app.core.contracts.responses import DryRunPreview, OperationResult
from app.core.interfaces.unit_of_work import IUnitOfWork
from app.core.policies.write_policy.pipeline import apply_write_plan, build_write_plan
from app.core.validation.integrity_validation import validate_update_integrity
from app.core.validation.semantic_validation import validate_update_semantics


def execute_update_memory(request: MemoryUpdateRequest, uow: IUnitOfWork) -> OperationResult:
    """This function orchestrates update flow with deterministic side-effect policy hooks."""

    semantic_errors = validate_update_semantics(request)
    if semantic_errors:
        return OperationResult(status="error", errors=semantic_errors)

    integrity_errors = validate_update_integrity(request, uow)
    if integrity_errors:
        return OperationResult(status="error", errors=integrity_errors)

    payload = request.model_dump(mode="python")
    plan = build_write_plan(payload)
    if request.mode == "dry_run":
        preview = DryRunPreview(accepted=True, planned_side_effects=plan)
        return OperationResult(status="ok", data=preview.model_dump(mode="python"))

    apply_write_plan(plan, uow)
    return OperationResult(status="ok", data={"memory_id": request.memory_id, "planned_side_effects": plan})
