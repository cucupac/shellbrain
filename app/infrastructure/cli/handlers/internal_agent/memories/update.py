"""Agent operation workflow for updating memories."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from app.core.contracts.errors import DomainValidationError, ErrorCode, ErrorDetail
from app.core.contracts.memories import MemoryBatchUpdateRequest, MemoryUpdateRequest
from app.core.entities.runtime_context import OperationDispatchTelemetryContext
from app.infrastructure.cli.handlers.command_context import OperationDependencies
from app.infrastructure.cli.handlers.result_envelopes import (
    ReturnHandledError,
    dump_errors,
    error_response,
    infer_error_stage_from_errors,
    ok_envelope,
)
from app.infrastructure.cli.handlers.internal_agent.memories.utility_vote_evidence import (
    attach_guidance,
    build_guidance_payloads,
)
from app.infrastructure.cli.handlers.command_context import ensure_telemetry_context
from app.infrastructure.cli.handlers.internal_agent.memories.utility_vote_evidence import (
    hydrate_update_request_evidence_from_session_state,
)
from app.infrastructure.cli.handlers.session_state import SessionStateManager
from app.core.use_cases.memories.update import execute_update_memory


def run_update_memory_operation(
    request: MemoryUpdateRequest | MemoryBatchUpdateRequest | None,
    *,
    dependencies: OperationDependencies,
    uow_factory,
    inferred_repo_id: str,
    validation_errors: tuple[ErrorDetail, ...] | list[ErrorDetail] = (),
    validation_error_stage: str = "schema_validation",
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    """Dispatch a typed update request to the update use-case."""

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
    session_state = session_manager.load_active_state(
        repo_root=resolved_repo_root,
        caller_identity=resolved_telemetry_context.caller_identity,
    )
    result: dict | None = None
    error_stage: str | None = None
    try:
        policy_errors = list(dependencies.update_policy_errors)
        if policy_errors:
            error_stage = infer_error_stage_from_errors(
                dump_errors(policy_errors), default_stage="contract_validation"
            )
            result = error_response(policy_errors)
        elif validation_errors:
            error_stage = infer_error_stage_from_errors(
                dump_errors(validation_errors), default_stage=validation_error_stage
            )
            result = error_response(validation_errors)
        elif request is None:
            error_stage = "contract_validation"
            result = error_response(
                [
                    ErrorDetail(
                        code=ErrorCode.SCHEMA_ERROR,
                        message="update request is required",
                    )
                ]
            )
        else:
            request, hydration_errors = (
                hydrate_update_request_evidence_from_session_state(
                    request=request,
                    session_state=session_state,
                )
            )
            if hydration_errors:
                error_stage = infer_error_stage_from_errors(
                    dump_errors(hydration_errors),
                    default_stage="semantic_validation",
                )
                result = error_response(hydration_errors)
                request = None
                raise ReturnHandledError()
            with uow_factory() as uow:
                result = ok_envelope(
                    execute_update_memory(
                        request,
                        uow,
                        id_generator=dependencies.id_generator,
                        policy_settings=dependencies.update_policy,
                    )
                )
                guidance = build_guidance_payloads(
                    uow_factory=uow_factory,
                    repo_id=inferred_repo_id,
                    caller_identity=resolved_telemetry_context.caller_identity,
                    session_state=session_state,
                    now_iso=dependencies.clock.now().isoformat(),
                    strong=False,
                )
                if guidance:
                    attach_guidance(result, guidance)
                    if (
                        session_state is not None
                        and session_state.current_problem_id is not None
                    ):
                        session_manager.record_guidance(
                            repo_root=resolved_repo_root,
                            caller_identity=resolved_telemetry_context.caller_identity,
                            problem_id=session_state.current_problem_id,
                        )
    except DomainValidationError as exc:
        error_stage = infer_error_stage_from_errors(
            dump_errors(exc.errors), default_stage="semantic_validation"
        )
        result = error_response(exc.errors)
    except ReturnHandledError:
        pass
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = error_response(
            [ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))]
        )

    assert result is not None
    dependencies.telemetry_sink.record(
        command="update",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        request=request,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
    )
    return result
