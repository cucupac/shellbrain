"""Agent operation workflow for reading host events."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from time import perf_counter

from app.core.errors import ErrorCode, ErrorDetail
from app.core.use_cases.episodes.events.request import EpisodeEventsRequest
from app.core.entities.runtime_context import (
    OperationDispatchTelemetryContext,
    SessionSelectionSummary,
)
from app.startup.operation_dependencies import OperationDependencies
from app.entrypoints.cli.handlers.result_envelopes import (
    dump_errors,
    error_response,
    infer_error_stage_from_errors,
    ok_envelope,
)
from app.entrypoints.cli.handlers.internal_agent.episodes.selection import (
    EventsSelectionError,
    resolve_events_source,
    selection_summary_from_events_source,
)
from app.startup.operation_dependencies import ensure_telemetry_context
from app.entrypoints.cli.handlers.internal_agent.episodes.serialization import serialize_episode_event
from app.entrypoints.cli.handlers.session_state import SessionStateManager
from app.core.use_cases.episodes.sync_episode import SyncEpisodeRequest, sync_episode


def run_read_events_operation(
    request: EpisodeEventsRequest | None,
    *,
    dependencies: OperationDependencies,
    uow_factory,
    inferred_repo_id: str,
    validation_errors: tuple[ErrorDetail, ...] | list[ErrorDetail] = (),
    validation_error_stage: str = "schema_validation",
    repo_root: Path | None = None,
    search_roots_by_host: dict[str, list[Path]] | None = None,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
):
    """Dispatch a typed events request to the active-episode browsing flow."""

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
    result: dict | None = None
    error_stage: str | None = None
    selection_summary = SessionSelectionSummary()
    sync_run_payload = None
    model_usage_records = ()
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
                        message="events request is required",
                    )
                ]
            )
        elif request.episode_id is not None:
            result, selection_summary = _read_exact_episode_events(
                request=request,
                uow_factory=uow_factory,
            )
            if result.get("status") == "error":
                error_stage = "episode_lookup"
        else:
            source = resolve_events_source(
                dependencies=dependencies,
                repo_root=resolved_repo_root,
                search_roots_by_host=search_roots_by_host,
                runtime_context=resolved_telemetry_context,
            )
            selection_summary = selection_summary_from_events_source(source)
            sync_started_at = perf_counter()
            try:
                normalized_events = dependencies.normalize_host_transcript(
                    host_app=str(source.host_app),
                    host_session_key=str(source.host_session_key),
                    transcript_path=Path(str(source.transcript_path)),
                )
                with uow_factory() as uow:
                    sync_result = sync_episode(
                        SyncEpisodeRequest.from_raw_events(
                            repo_id=request.repo_id,
                            host_app=str(source.host_app),
                            host_session_key=str(source.host_session_key),
                            thread_id=str(source.canonical_thread_id),
                            transcript_path=str(source.transcript_path),
                            normalized_events=normalized_events,
                        ),
                        uow=uow,
                        clock=dependencies.clock,
                        id_generator=dependencies.id_generator,
                    )
                    events = uow.episodes.list_recent_events(
                        repo_id=request.repo_id,
                        episode_id=sync_result.episode_id,
                        limit=request.limit,
                    )
                    if request.order == "oldest_first":
                        events = list(reversed(events))
                    result = ok_envelope(
                        {
                            "episode_id": sync_result.episode_id,
                            "host_app": source.host_app,
                            "thread_id": sync_result.thread_id,
                            "events": [
                                serialize_episode_event(event) for event in events
                            ],
                        }
                    )
                selection_summary = replace(
                    selection_summary,
                    selected_episode_id=sync_result.episode_id,
                )
                if source.trusted:
                    session_manager.record_events(
                        repo_root=resolved_repo_root,
                        caller_identity=resolved_telemetry_context.caller_identity,
                        episode_id=sync_result.episode_id,
                        event_ids=[
                            str(event["id"]) for event in result["data"]["events"]
                        ],
                    )
                sync_run_payload = {
                    "sync_run_id": dependencies.id_generator.new_id(),
                    "source": "events_inline",
                    "invocation_id": resolved_telemetry_context.invocation_id,
                    "repo_id": request.repo_id,
                    "host_app": str(source.host_app),
                    "host_session_key": str(source.host_session_key),
                    "thread_id": sync_result.thread_id,
                    "episode_id": sync_result.episode_id,
                    "transcript_path": sync_result.transcript_path,
                    "outcome": "ok",
                    "error_stage": None,
                    "error_message": None,
                    "duration_ms": int((perf_counter() - sync_started_at) * 1000),
                    "imported_event_count": sync_result.imported_event_count,
                    "total_event_count": sync_result.total_event_count,
                    "user_event_count": sync_result.user_event_count,
                    "assistant_event_count": sync_result.assistant_event_count,
                    "tool_event_count": sync_result.tool_event_count,
                    "system_event_count": sync_result.system_event_count,
                    "tool_type_counts": dict(sync_result.tool_type_counts),
                    "created_at": dependencies.clock.now(),
                }
                try:
                    model_usage_records = tuple(
                        dependencies.collect_model_usage_records_for_session(
                            repo_id=request.repo_id,
                            host_app=str(source.host_app),
                            host_session_key=str(source.host_session_key),
                            thread_id=sync_result.thread_id,
                            episode_id=sync_result.episode_id,
                            transcript_path=Path(sync_result.transcript_path),
                        )
                    )
                except Exception:
                    model_usage_records = ()
            except Exception as exc:
                error_stage = "sync"
                result = error_response(
                    [ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))]
                )
                sync_run_payload = {
                    "sync_run_id": dependencies.id_generator.new_id(),
                    "source": "events_inline",
                    "invocation_id": resolved_telemetry_context.invocation_id,
                    "repo_id": request.repo_id,
                    "host_app": str(source.host_app),
                    "host_session_key": str(source.host_session_key),
                    "thread_id": selection_summary.selected_thread_id
                    or str(source.canonical_thread_id),
                    "episode_id": selection_summary.selected_episode_id,
                    "transcript_path": str(source.transcript_path),
                    "outcome": "error",
                    "error_stage": "sync",
                    "error_message": str(exc),
                    "duration_ms": int((perf_counter() - sync_started_at) * 1000),
                    "imported_event_count": 0,
                    "total_event_count": 0,
                    "user_event_count": 0,
                    "assistant_event_count": 0,
                    "tool_event_count": 0,
                    "system_event_count": 0,
                    "tool_type_counts": {},
                    "created_at": dependencies.clock.now(),
                }
    except EventsSelectionError as exc:
        error_stage = "session_selection"
        result = error_response([exc.error])
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = error_response(
            [ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))]
        )

    assert result is not None
    dependencies.telemetry_sink.record(
        command="events",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        request=request,
        selection_summary=selection_summary,
        sync_run_payload=sync_run_payload,
        model_usage_records=model_usage_records,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
    )
    return result


def _read_exact_episode_events(
    *,
    request: EpisodeEventsRequest,
    uow_factory,
) -> tuple[dict, SessionSelectionSummary]:
    """Read already-stored events for an explicit episode id without syncing."""

    assert request.episode_id is not None
    with uow_factory() as uow:
        episode = uow.episodes.get_episode(
            repo_id=request.repo_id,
            episode_id=request.episode_id,
        )
        if episode is None:
            return error_response(
                [
                    ErrorDetail(
                        code=ErrorCode.NOT_FOUND,
                        message=f"episode not found: {request.episode_id}",
                        field="episode_id",
                    )
                ]
            ), SessionSelectionSummary(selected_episode_id=request.episode_id)
        range_payload = None
        if request.up_to_seq is not None:
            after_seq = request.after_seq if request.after_seq is not None else 0
            events = uow.episodes.list_events_range(
                repo_id=request.repo_id,
                episode_id=request.episode_id,
                after_seq=after_seq,
                up_to_seq=request.up_to_seq,
            )
            range_payload = {
                "after_seq": after_seq,
                "up_to_seq": request.up_to_seq,
                "order": "oldest_first",
                "returned_count": len(events),
                "expected_count": request.up_to_seq - after_seq,
                "complete": len(events) == request.up_to_seq - after_seq,
            }
        else:
            events = uow.episodes.list_recent_events(
                repo_id=request.repo_id,
                episode_id=request.episode_id,
                limit=request.limit,
            )
            if request.order == "oldest_first":
                events = list(reversed(events))
    data = {
        "episode_id": episode.id,
        "host_app": episode.host_app,
        "thread_id": episode.thread_id,
        "events": [serialize_episode_event(event) for event in events],
    }
    if range_payload is not None:
        data["event_range"] = range_payload
    return ok_envelope(data), SessionSelectionSummary(
        selected_host_app=episode.host_app,
        selected_thread_id=episode.thread_id,
        selected_episode_id=episode.id,
    )
