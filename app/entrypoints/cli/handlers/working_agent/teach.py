"""Working-agent operation for explicit Shellbrain teaching."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter

from app.core.errors import ErrorCode, ErrorDetail
from app.core.entities.runtime_context import (
    OperationDispatchTelemetryContext,
    SessionSelectionSummary,
)
from app.core.use_cases.knowledge_builder.teach_knowledge import (
    TeachKnowledgeRequest,
    execute_teach_knowledge,
)
from app.entrypoints.cli.handlers.dependencies import (
    OperationDependencies,
    ensure_telemetry_context,
)
from app.entrypoints.cli.handlers.result_envelopes import (
    dump_errors,
    error_response,
    infer_error_stage_from_errors,
    ok_envelope,
)


def run_teach_operation(
    request: TeachKnowledgeRequest | None,
    *,
    dependencies: OperationDependencies,
    uow_factory,
    inferred_repo_id: str,
    validation_errors: tuple[ErrorDetail, ...] | list[ErrorDetail] = (),
    validation_error_stage: str = "schema_validation",
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    """Persist explicit teaching evidence and run the teach knowledge agent."""

    started_at = perf_counter()
    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_telemetry_context = ensure_telemetry_context(
        dependencies=dependencies,
        telemetry_context=telemetry_context,
        repo_root=resolved_repo_root,
    )
    result: dict | None = None
    error_stage: str | None = None
    selection_summary = _selection_summary_from_context(resolved_telemetry_context)
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
                        code=ErrorCode.SCHEMA_ERROR,
                        message="teach request is required",
                    )
                ]
            )
        else:
            teaching_result = execute_teach_knowledge(
                request,
                uow_factory=uow_factory,
                clock=dependencies.clock,
                id_generator=dependencies.id_generator,
                settings=dependencies.teach_knowledge_settings,
                agent_runner=dependencies.teach_knowledge_inner_agent_runner,
                caller_identity=resolved_telemetry_context.caller_identity,
            )
            result = ok_envelope(teaching_result.to_response_data())
            selection_summary = _selection_summary_from_teach_result(
                result=result,
                fallback=selection_summary,
            )
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = error_response(
            [ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))]
        )

    assert result is not None
    dependencies.telemetry_sink.record(
        command="teach",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        request=request,
        selection_summary=selection_summary,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
    )
    return result


def _selection_summary_from_context(
    context: OperationDispatchTelemetryContext,
) -> SessionSelectionSummary:
    """Return caller-derived selection context when available."""

    caller_identity = context.caller_identity
    if caller_identity is None:
        return SessionSelectionSummary(
            selected_host_app="shellbrain",
            selected_host_session_key="teach",
            selected_thread_id="shellbrain:teach",
            matching_candidate_count=1,
        )
    return SessionSelectionSummary(
        selected_host_app=caller_identity.host_app,
        selected_host_session_key=caller_identity.host_session_key,
        selected_thread_id=caller_identity.canonical_id,
        matching_candidate_count=1,
    )


def _selection_summary_from_teach_result(
    *, result: dict, fallback: SessionSelectionSummary
) -> SessionSelectionSummary:
    """Attach the persisted episode id to telemetry selection metadata."""

    data = result.get("data", {})
    if not isinstance(data, dict):
        return fallback
    episode_id = data.get("episode_id")
    if not isinstance(episode_id, str):
        return fallback
    return SessionSelectionSummary(
        selected_host_app=fallback.selected_host_app,
        selected_host_session_key=fallback.selected_host_session_key,
        selected_thread_id=fallback.selected_thread_id,
        selected_episode_id=episode_id,
        matching_candidate_count=fallback.matching_candidate_count,
        selection_ambiguous=fallback.selection_ambiguous,
    )
