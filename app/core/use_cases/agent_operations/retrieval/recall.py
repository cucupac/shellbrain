"""Agent operation workflow for worker recall briefs."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.requests import MemoryRecallRequest
from app.core.entities.telemetry import OperationDispatchTelemetryContext
from app.core.observability.telemetry.operation_records import infer_error_stage_from_errors
from app.core.use_cases.agent_operations.dependencies import OperationDependencies
from app.core.use_cases.agent_operations.errors import dump_errors, error_response
from app.core.use_cases.agent_operations.operation_telemetry import ensure_telemetry_context, persist_operation_telemetry_best_effort
from app.core.use_cases.agent_operations.retrieval_execution import execute_recall_memory_with_dependencies
from app.core.use_cases.manage_session_state import SessionStateManager


def run_recall_memory_operation(
    request: MemoryRecallRequest | None,
    *,
    dependencies: OperationDependencies,
    uow_factory,
    inferred_repo_id: str,
    validation_errors: list[ErrorDetail] | None = None,
    validation_error_stage: str = "schema_validation",
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    """Dispatch a typed read-only recall request."""

    started_at = perf_counter()
    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_telemetry_context = ensure_telemetry_context(
        dependencies=dependencies,
        telemetry_context=telemetry_context,
        repo_root=resolved_repo_root,
    )
    session_manager = SessionStateManager(store=dependencies.session_state_store, clock=dependencies.clock)
    session_manager.load_active_state(
        repo_root=resolved_repo_root,
        caller_identity=resolved_telemetry_context.caller_identity,
    )
    result: dict | None = None
    recall_telemetry: dict | None = None
    error_stage: str | None = None
    try:
        if validation_errors:
            error_stage = infer_error_stage_from_errors(dump_errors(validation_errors), default_stage=validation_error_stage)
            result = error_response(validation_errors)
        elif request is None:
            error_stage = "contract_validation"
            result = error_response([ErrorDetail(code=ErrorCode.SCHEMA_ERROR, message="recall request is required")])
        else:
            with uow_factory() as uow:
                result = execute_recall_memory_with_dependencies(request=request, uow=uow, dependencies=dependencies).model_dump(mode="python")
            data = result.get("data")
            if isinstance(data, dict):
                telemetry_payload = data.pop("_telemetry", None)
                if isinstance(telemetry_payload, dict):
                    recall_telemetry = telemetry_payload
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])

    assert result is not None
    persist_operation_telemetry_best_effort(
        command="recall",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        request=request,
        recall_telemetry=recall_telemetry,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
        dependencies=dependencies,
    )
    return result
