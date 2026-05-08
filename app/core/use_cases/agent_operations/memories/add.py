"""Agent operation workflow for adding memories."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.requests import MemoryCreateRequest
from app.core.entities.telemetry import OperationDispatchTelemetryContext
from app.core.observability.telemetry.operation_records import infer_error_stage_from_errors
from app.core.use_cases.agent_operations.dependencies import OperationDependencies
from app.core.use_cases.agent_operations.errors import dump_errors, error_response
from app.core.use_cases.agent_operations.guidance import (
    attach_guidance,
    build_guidance_payloads,
)
from app.core.use_cases.agent_operations.operation_telemetry import ensure_telemetry_context, persist_operation_telemetry_best_effort
from app.core.use_cases.agent_operations.validation import validate_create_request
from app.core.use_cases.manage_session_state import SessionStateManager
from app.core.use_cases.memories.create_memory import execute_create_memory


def run_create_memory_operation(
    request: MemoryCreateRequest | None,
    *,
    dependencies: OperationDependencies,
    uow_factory,
    embedding_provider_factory,
    embedding_model: str,
    inferred_repo_id: str,
    validation_errors: list[ErrorDetail] | None = None,
    validation_error_stage: str = "schema_validation",
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    """Dispatch a typed create request to the create use-case."""

    started_at = perf_counter()
    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_telemetry_context = ensure_telemetry_context(
        dependencies=dependencies,
        telemetry_context=telemetry_context,
        repo_root=resolved_repo_root,
    )
    session_manager = SessionStateManager(store=dependencies.session_state_store, clock=dependencies.clock)
    result: dict | None = None
    error_stage: str | None = None

    try:
        policy_errors = list(dependencies.create_policy_errors)
        if policy_errors:
            error_stage = infer_error_stage_from_errors(dump_errors(policy_errors), default_stage="contract_validation")
            result = error_response(policy_errors)
        elif validation_errors:
            error_stage = infer_error_stage_from_errors(dump_errors(validation_errors), default_stage=validation_error_stage)
            result = error_response(validation_errors)
        elif request is None:
            error_stage = "contract_validation"
            result = error_response([ErrorDetail(code=ErrorCode.SCHEMA_ERROR, message="create request is required")])
        else:
            policy = dependencies.create_policy
            with uow_factory() as uow:
                validation_errors = validate_create_request(request, uow=uow, gates=list(policy.gates))
                if validation_errors:
                    error_stage = infer_error_stage_from_errors(
                        dump_errors(validation_errors),
                        default_stage="semantic_validation",
                    )
                    result = error_response(validation_errors)
                else:
                    embedding_provider = embedding_provider_factory()
                    result = execute_create_memory(
                        request,
                        uow,
                        embedding_provider=embedding_provider,
                        embedding_model=embedding_model,
                    ).model_dump(mode="python")
                    if result.get("status") == "ok":
                        session_state = session_manager.load_active_state(
                            repo_root=resolved_repo_root,
                            caller_identity=resolved_telemetry_context.caller_identity,
                        )
                        request_links = request.memory.links
                        if request.memory.kind == "problem":
                            session_state = session_manager.record_problem(
                                repo_root=resolved_repo_root,
                                caller_identity=resolved_telemetry_context.caller_identity,
                                problem_id=str(result["data"]["memory_id"]),
                            )
                        elif request.memory.kind in {"solution", "failed_tactic"} and request_links.problem_id:
                            session_state = session_manager.record_problem(
                                repo_root=resolved_repo_root,
                                caller_identity=resolved_telemetry_context.caller_identity,
                                problem_id=request_links.problem_id,
                            )
                        strong_guidance = request.memory.kind == "solution"
                        guidance = build_guidance_payloads(
                            uow_factory=uow_factory,
                            repo_id=inferred_repo_id,
                            caller_identity=resolved_telemetry_context.caller_identity,
                            session_state=session_state,
                            now_iso=dependencies.clock.now().isoformat(),
                            strong=strong_guidance,
                        )
                        if guidance:
                            attach_guidance(result, guidance)
                            if session_state is not None and session_state.current_problem_id is not None:
                                session_manager.record_guidance(
                                    repo_root=resolved_repo_root,
                                    caller_identity=resolved_telemetry_context.caller_identity,
                                    problem_id=session_state.current_problem_id,
                                )
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])

    assert result is not None
    persist_operation_telemetry_best_effort(
        command="create",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        request=request,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
        dependencies=dependencies,
    )
    return result
