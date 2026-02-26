"""This module defines the create-memory use-case orchestration entry point."""

from uuid import uuid4

from app.core.contracts.requests import MemoryCreateRequest
from app.core.contracts.responses import OperationResult
from app.core.policies.write_policy.pipeline import apply_write_plan, build_write_plan
from app.core.validation.integrity_validation import validate_create_integrity
from app.core.validation.semantic_validation import validate_create_semantics
from app.core.interfaces.unit_of_work import IUnitOfWork


def execute_create_memory(request: MemoryCreateRequest, uow: IUnitOfWork) -> OperationResult:
    """This function orchestrates create flow with validation and write policy hooks."""

    semantic_errors = validate_create_semantics(request)
    if semantic_errors:
        return OperationResult(status="error", errors=semantic_errors)

    integrity_errors = validate_create_integrity(request, uow)
    if integrity_errors:
        return OperationResult(status="error", errors=integrity_errors)

    memory_id = str(uuid4())
    payload = request.model_dump(mode="python")
    payload["memory_id"] = memory_id
    plan = build_write_plan(payload)
    apply_write_plan(plan, uow)
    return OperationResult(status="ok", data={"memory_id": memory_id, "planned_side_effects": plan})
