"""Agent operation workflow for reading memory context."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.retrieval import MemoryReadRequest
from app.core.entities.runtime_context import OperationDispatchTelemetryContext
from app.handlers.command_context import OperationDependencies
from app.handlers.result_envelopes import (
    dump_errors,
    error_response,
    infer_error_stage_from_errors,
    ok_envelope,
)
from app.handlers.telemetry_sink import ensure_telemetry_context
from app.handlers.internal_agent.retrieval.execution import (
    execute_read_memory_with_dependencies,
)
from app.handlers.session_state import SessionStateManager


def run_read_memory_operation(
    request: MemoryReadRequest | None,
    *,
    dependencies: OperationDependencies,
    uow_factory,
    inferred_repo_id: str,
    validation_errors: tuple[ErrorDetail, ...] | list[ErrorDetail] = (),
    validation_error_stage: str = "schema_validation",
    requested_limit: int | None = None,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    """Dispatch a typed read request to the read use-case."""

    started_at = perf_counter()
    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_telemetry_context = ensure_telemetry_context(
        dependencies=dependencies,
        telemetry_context=telemetry_context,
        repo_root=resolved_repo_root,
    )
    session_manager = SessionStateManager(
        store=dependencies.session_state_store, clock=dependencies.clock
    )
    session_manager.load_active_state(
        repo_root=resolved_repo_root,
        caller_identity=resolved_telemetry_context.caller_identity,
    )
    result: dict | None = None
    error_stage: str | None = None
    try:
        if validation_errors:
            error_stage = infer_error_stage_from_errors(
                dump_errors(validation_errors), default_stage=validation_error_stage
            )
            result = error_response(validation_errors)
        elif request is None:
            error_stage = "contract_validation"
            result = error_response(
                [
                    ErrorDetail(
                        code=ErrorCode.SCHEMA_ERROR, message="read request is required"
                    )
                ]
            )
        else:
            with uow_factory() as uow:
                result = ok_envelope(
                    execute_read_memory_with_dependencies(
                        request=request, uow=uow, dependencies=dependencies
                    )
                )
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = error_response(
            [ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))]
        )

    assert result is not None
    dependencies.telemetry_sink.record(
        command="read",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        request=request,
        requested_limit=requested_limit,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
    )
    return result
