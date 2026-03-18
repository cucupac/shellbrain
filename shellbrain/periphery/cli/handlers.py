"""This module defines CLI command handlers that dispatch to core use-case functions."""

from dataclasses import replace
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from shellbrain.boot.create_policy import get_create_hydration_defaults, get_create_policy_settings, validate_create_policy_settings
from shellbrain.boot.read_policy import get_read_hydration_defaults
from shellbrain.boot.update_policy import get_update_policy_settings, validate_update_policy_settings
from shellbrain.core.contracts.errors import ErrorCode, ErrorDetail
from shellbrain.core.contracts.requests import EpisodeEventsRequest, MemoryCreateRequest, MemoryUpdateRequest
from shellbrain.core.contracts.responses import OperationResult
from shellbrain.core.entities.telemetry import OperationDispatchTelemetryContext, SessionSelectionSummary
from shellbrain.core.use_cases.create_memory import execute_create_memory
from shellbrain.core.use_cases.read_memory import execute_read_memory
from shellbrain.core.use_cases.record_episode_sync_telemetry import record_episode_sync_telemetry
from shellbrain.core.use_cases.record_operation_telemetry import record_operation_telemetry
from shellbrain.core.use_cases.sync_episode import sync_episode_from_host
from shellbrain.core.use_cases.update_memory import execute_update_memory
from shellbrain.periphery.cli.hydration import (
    hydrate_create_payload,
    hydrate_events_payload,
    hydrate_read_payload,
    hydrate_update_payload,
)
from shellbrain.periphery.cli.schema_validation import (
    validate_create_schema,
    validate_events_schema,
    validate_internal_create_contract,
    validate_internal_events_contract,
    validate_internal_read_contract,
    validate_internal_update_contract,
    validate_read_schema,
    validate_update_schema,
)
from shellbrain.periphery.telemetry import get_operation_telemetry_context
from shellbrain.periphery.telemetry.operation_summary import (
    build_operation_invocation_record,
    build_read_summary_records,
    build_write_summary_records,
    infer_error_stage_from_errors,
)
from shellbrain.periphery.telemetry.session_selection import (
    EventsDiscoveryCandidate,
    discover_events_candidate,
    summarize_runtime_selection,
)
from shellbrain.periphery.telemetry.sync_summary import build_episode_sync_records
from shellbrain.periphery.validation.integrity_validation import validate_create_integrity, validate_update_integrity
from shellbrain.periphery.validation.semantic_validation import validate_create_semantics, validate_update_semantics


def _error_response(errors: list[ErrorDetail]) -> dict:
    """This function builds a standardized error response envelope for CLI handlers."""

    return OperationResult(status="error", errors=errors).model_dump(mode="python")


def _validate_create_request(request: MemoryCreateRequest, *, uow, gates: list[str]) -> list[ErrorDetail]:
    """Run non-schema create validations before invoking core execution."""

    if "semantic" in gates:
        semantic_errors = validate_create_semantics(request)
        if semantic_errors:
            return semantic_errors
    if "integrity" in gates:
        return validate_create_integrity(request, uow)
    return []


def _validate_update_request(request: MemoryUpdateRequest, *, uow, gates: list[str]) -> list[ErrorDetail]:
    """Run non-schema update validations before invoking core execution."""

    if "semantic" in gates:
        semantic_errors = validate_update_semantics(request)
        if semantic_errors:
            return semantic_errors
    if "integrity" in gates:
        return validate_update_integrity(request, uow)
    return []


def handle_create(
    payload: dict,
    *,
    uow_factory,
    embedding_provider_factory,
    embedding_model: str,
    inferred_repo_id: str,
    defaults: dict | None = None,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
):
    """This function validates and dispatches a create payload to the create use-case."""

    started_at = perf_counter()
    resolved_telemetry_context = _ensure_telemetry_context(
        telemetry_context=telemetry_context,
        repo_root=None,
    )
    request: MemoryCreateRequest | None = None
    result: dict | None = None
    error_stage: str | None = None

    try:
        policy_errors = validate_create_policy_settings()
        if policy_errors:
            error_stage = infer_error_stage_from_errors(_dump_errors(policy_errors), default_stage="contract_validation")
            result = _error_response(policy_errors)
        else:
            policy = get_create_policy_settings()
            agent_request, errors = validate_create_schema(payload)
            if errors:
                error_stage = infer_error_stage_from_errors(_dump_errors(errors), default_stage="schema_validation")
                result = _error_response(errors)
            else:
                assert agent_request is not None
                resolved_defaults = defaults if defaults is not None else get_create_hydration_defaults()
                hydrated_payload = hydrate_create_payload(
                    agent_request.model_dump(mode="python", exclude_none=True),
                    inferred_repo_id=inferred_repo_id,
                    defaults=resolved_defaults,
                )
                request, contract_errors = validate_internal_create_contract(hydrated_payload)
                if contract_errors:
                    error_stage = infer_error_stage_from_errors(
                        _dump_errors(contract_errors),
                        default_stage="contract_validation",
                    )
                    result = _error_response(contract_errors)
                else:
                    assert request is not None
                    with uow_factory() as uow:
                        validation_errors = _validate_create_request(request, uow=uow, gates=policy["gates"])
                        if validation_errors:
                            error_stage = infer_error_stage_from_errors(
                                _dump_errors(validation_errors),
                                default_stage="semantic_validation",
                            )
                            result = _error_response(validation_errors)
                        else:
                            embedding_provider = embedding_provider_factory()
                            result = execute_create_memory(
                                request,
                                uow,
                                embedding_provider=embedding_provider,
                                embedding_model=embedding_model,
                            ).model_dump(mode="python")
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])

    assert result is not None
    _persist_operation_telemetry_best_effort(
        command="create",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        request=request,
        agent_payload=payload,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
    )
    return result


def handle_read(
    payload: dict,
    *,
    uow_factory,
    inferred_repo_id: str,
    defaults: dict | None = None,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
):
    """This function validates and dispatches a read payload to the read use-case."""

    started_at = perf_counter()
    resolved_telemetry_context = _ensure_telemetry_context(
        telemetry_context=telemetry_context,
        repo_root=None,
    )
    request = None
    result: dict | None = None
    error_stage: str | None = None
    try:
        agent_request, errors = validate_read_schema(payload)
        if errors:
            error_stage = infer_error_stage_from_errors(_dump_errors(errors), default_stage="schema_validation")
            result = _error_response(errors)
        else:
            assert agent_request is not None
            resolved_defaults = defaults if defaults is not None else get_read_hydration_defaults()
            hydrated_payload = hydrate_read_payload(
                agent_request.model_dump(mode="python", exclude_none=True),
                inferred_repo_id=inferred_repo_id,
                defaults=resolved_defaults,
            )
            request, contract_errors = validate_internal_read_contract(hydrated_payload)
            if contract_errors:
                error_stage = infer_error_stage_from_errors(
                    _dump_errors(contract_errors),
                    default_stage="contract_validation",
                )
                result = _error_response(contract_errors)
            else:
                assert request is not None
                with uow_factory() as uow:
                    result = execute_read_memory(request, uow).model_dump(mode="python")
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])

    assert result is not None
    _persist_operation_telemetry_best_effort(
        command="read",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        request=request,
        agent_payload=payload,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
    )
    return result


def handle_events(
    payload: dict,
    *,
    uow_factory,
    inferred_repo_id: str,
    repo_root: Path | None = None,
    search_roots_by_host: dict[str, list[Path]] | None = None,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
):
    """Validate and dispatch an events payload to the active-episode browsing flow."""

    started_at = perf_counter()
    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_telemetry_context = _ensure_telemetry_context(
        telemetry_context=telemetry_context,
        repo_root=resolved_repo_root,
    )
    request = None
    result: dict | None = None
    error_stage: str | None = None
    selection_summary = SessionSelectionSummary()
    sync_run = None
    sync_tool_types = ()
    try:
        agent_request, errors = validate_events_schema(payload)
        if errors:
            error_stage = infer_error_stage_from_errors(_dump_errors(errors), default_stage="schema_validation")
            result = _error_response(errors)
        else:
            assert agent_request is not None
            hydrated_payload = hydrate_events_payload(
                agent_request.model_dump(mode="python", exclude_none=True),
                inferred_repo_id=inferred_repo_id,
            )
            request, contract_errors = validate_internal_events_contract(hydrated_payload)
            if contract_errors:
                error_stage = infer_error_stage_from_errors(
                    _dump_errors(contract_errors),
                    default_stage="contract_validation",
                )
                result = _error_response(contract_errors)
            else:
                assert request is not None
                discovery = _resolve_events_candidate(
                    request,
                    repo_root=resolved_repo_root,
                    search_roots_by_host=search_roots_by_host,
                )
                selection_summary = discovery.summary
                sync_started_at = perf_counter()
                try:
                    with uow_factory() as uow:
                        sync_result = sync_episode_from_host(
                            repo_id=request.repo_id,
                            host_app=discovery.host_app,
                            host_session_key=discovery.host_session_key,
                            uow=uow,
                            search_roots=discovery.search_roots,
                            last_known_path=discovery.transcript_path,
                        )
                        events = uow.episodes.list_recent_events(
                            repo_id=request.repo_id,
                            episode_id=str(sync_result["episode_id"]),
                            limit=request.limit,
                        )
                        result = OperationResult(
                            status="ok",
                            data={
                                "episode_id": sync_result["episode_id"],
                                "host_app": discovery.host_app,
                                "thread_id": sync_result["thread_id"],
                                "events": [_serialize_episode_event(event) for event in events],
                            },
                        ).model_dump(mode="python")
                    selection_summary = replace(selection_summary, selected_episode_id=str(sync_result["episode_id"]))
                    sync_run, sync_tool_types = build_episode_sync_records(
                        sync_run_id=str(uuid4()),
                        source="events_inline",
                        invocation_id=resolved_telemetry_context.invocation_id,
                        repo_id=request.repo_id,
                        host_app=discovery.host_app,
                        host_session_key=discovery.host_session_key,
                        thread_id=str(sync_result["thread_id"]),
                        episode_id=str(sync_result["episode_id"]),
                        transcript_path=str(sync_result["transcript_path"]),
                        outcome="ok",
                        error_stage=None,
                        error_message=None,
                        duration_ms=int((perf_counter() - sync_started_at) * 1000),
                        imported_event_count=int(sync_result["imported_event_count"]),
                        total_event_count=int(sync_result["total_event_count"]),
                        user_event_count=int(sync_result["user_event_count"]),
                        assistant_event_count=int(sync_result["assistant_event_count"]),
                        tool_event_count=int(sync_result["tool_event_count"]),
                        system_event_count=int(sync_result["system_event_count"]),
                        tool_type_counts=dict(sync_result["tool_type_counts"]),
                    )
                except Exception as exc:
                    error_stage = "sync"
                    result = _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])
                    sync_run, sync_tool_types = build_episode_sync_records(
                        sync_run_id=str(uuid4()),
                        source="events_inline",
                        invocation_id=resolved_telemetry_context.invocation_id,
                        repo_id=request.repo_id,
                        host_app=discovery.host_app,
                        host_session_key=discovery.host_session_key,
                        thread_id=selection_summary.selected_thread_id or f"{discovery.host_app}:{discovery.host_session_key}",
                        episode_id=selection_summary.selected_episode_id,
                        transcript_path=str(discovery.transcript_path),
                        outcome="error",
                        error_stage="sync",
                        error_message=str(exc),
                        duration_ms=int((perf_counter() - sync_started_at) * 1000),
                        imported_event_count=0,
                        total_event_count=0,
                        user_event_count=0,
                        assistant_event_count=0,
                        tool_event_count=0,
                        system_event_count=0,
                        tool_type_counts={},
                    )
    except _EventsSelectionError as exc:
        error_stage = "session_selection"
        result = _error_response([exc.error])
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])

    assert result is not None
    _persist_operation_telemetry_best_effort(
        command="events",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        request=request,
        selection_summary=selection_summary,
        sync_run=sync_run,
        sync_tool_types=sync_tool_types,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
    )
    return result


def handle_update(
    payload: dict,
    *,
    uow_factory,
    inferred_repo_id: str,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
):
    """This function validates and dispatches an update payload to the update use-case."""

    started_at = perf_counter()
    resolved_telemetry_context = _ensure_telemetry_context(
        telemetry_context=telemetry_context,
        repo_root=None,
    )
    request = None
    result: dict | None = None
    error_stage: str | None = None
    try:
        policy_errors = validate_update_policy_settings()
        if policy_errors:
            error_stage = infer_error_stage_from_errors(_dump_errors(policy_errors), default_stage="contract_validation")
            result = _error_response(policy_errors)
        else:
            policy = get_update_policy_settings()
            agent_request, errors = validate_update_schema(payload)
            if errors:
                error_stage = infer_error_stage_from_errors(_dump_errors(errors), default_stage="schema_validation")
                result = _error_response(errors)
            else:
                assert agent_request is not None
                hydrated_payload = hydrate_update_payload(
                    agent_request.model_dump(mode="python", exclude_none=True),
                    inferred_repo_id=inferred_repo_id,
                )
                request, contract_errors = validate_internal_update_contract(hydrated_payload)
                if contract_errors:
                    error_stage = infer_error_stage_from_errors(
                        _dump_errors(contract_errors),
                        default_stage="contract_validation",
                    )
                    result = _error_response(contract_errors)
                else:
                    assert request is not None
                    with uow_factory() as uow:
                        validation_errors = _validate_update_request(request, uow=uow, gates=policy["gates"])
                        if validation_errors:
                            error_stage = infer_error_stage_from_errors(
                                _dump_errors(validation_errors),
                                default_stage="semantic_validation",
                            )
                            result = _error_response(validation_errors)
                        else:
                            result = execute_update_memory(request, uow).model_dump(mode="python")
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])

    assert result is not None
    _persist_operation_telemetry_best_effort(
        command="update",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        request=request,
        agent_payload=payload,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
    )
    return result


class _EventsSelectionError(Exception):
    """Internal control-flow exception for expected events selection failures."""

    def __init__(self, error: ErrorDetail) -> None:
        super().__init__(error.message)
        self.error = error


def _resolve_events_candidate(
    request: EpisodeEventsRequest,
    *,
    repo_root: Path,
    search_roots_by_host: dict[str, list[Path]] | None,
) -> EventsDiscoveryCandidate:
    """Resolve the newest active host session for an events request."""

    _ = request

    discovery = discover_events_candidate(
        repo_root=repo_root,
        search_roots_by_host=search_roots_by_host,
    )
    if discovery is None:
        raise _EventsSelectionError(
            ErrorDetail(
                code=ErrorCode.NOT_FOUND,
                message="No active host session found for this repo",
            )
        )
    return discovery


def _serialize_episode_event(event) -> dict:
    """Render one stored episode event into deterministic JSON-safe output."""

    content = str(event.content)
    try:
        parsed_content = json.loads(content)
    except json.JSONDecodeError:
        parsed_content = content
    created_at = event.created_at.isoformat() if event.created_at is not None else None
    return {
        "id": event.id,
        "seq": event.seq,
        "source": event.source.value if hasattr(event.source, "value") else str(event.source),
        "content": parsed_content,
        "created_at": created_at,
    }


def _ensure_telemetry_context(
    *,
    telemetry_context: OperationDispatchTelemetryContext | None,
    repo_root: Path | None,
) -> OperationDispatchTelemetryContext:
    """Return the active handler telemetry context or synthesize one for direct calls."""

    if telemetry_context is not None:
        return telemetry_context
    inherited = get_operation_telemetry_context()
    if inherited is not None:
        return inherited
    return OperationDispatchTelemetryContext(
        invocation_id=str(uuid4()),
        repo_root=str((repo_root or Path.cwd()).resolve()),
        no_sync=False,
    )


def _dump_errors(errors: list[ErrorDetail]) -> list[dict]:
    """Render structured errors into plain dicts for telemetry stage mapping."""

    return [error.model_dump(mode="python") for error in errors]


def _persist_operation_telemetry_best_effort(
    *,
    command: str,
    uow_factory,
    repo_id: str,
    telemetry_context: OperationDispatchTelemetryContext,
    result: dict,
    error_stage: str | None,
    request=None,
    agent_payload: dict | None = None,
    selection_summary: SessionSelectionSummary | None = None,
    sync_run=None,
    sync_tool_types=(),
    total_latency_ms: int | None = None,
) -> None:
    """Persist invocation telemetry in a second best-effort transaction."""

    try:
        with uow_factory() as telemetry_uow:
            resolved_selection = selection_summary
            if resolved_selection is None:
                resolved_selection = summarize_runtime_selection(
                    repo_root=Path(telemetry_context.repo_root),
                    repo_id=repo_id,
                    uow=telemetry_uow,
                )
            invocation = build_operation_invocation_record(
                invocation_id=telemetry_context.invocation_id,
                command=command,
                repo_id=repo_id,
                repo_root=telemetry_context.repo_root,
                no_sync=telemetry_context.no_sync,
                selection_summary=resolved_selection,
                result=result,
                error_stage=error_stage,
                total_latency_ms=total_latency_ms if total_latency_ms is not None else 0,
            )

            read_summary = None
            read_items = ()
            write_summary = None
            write_items = ()

            if result.get("status") == "ok" and command == "read" and request is not None:
                pack = result.get("data", {}).get("pack", {})
                if isinstance(pack, dict):
                    read_summary, read_items = build_read_summary_records(
                        invocation_id=telemetry_context.invocation_id,
                        agent_payload=agent_payload or {},
                        request=request,
                        pack=pack,
                    )

            if result.get("status") == "ok" and command in {"create", "update"} and request is not None:
                planned_side_effects = result.get("data", {}).get("planned_side_effects", [])
                if isinstance(planned_side_effects, list):
                    write_summary, write_items = build_write_summary_records(
                        invocation_id=telemetry_context.invocation_id,
                        command=command,
                        request=request,
                        planned_side_effects=planned_side_effects,
                    )

            record_operation_telemetry(
                uow=telemetry_uow,
                invocation=invocation,
                read_summary=read_summary,
                read_items=read_items,
                write_summary=write_summary,
                write_items=write_items,
            )
            if sync_run is not None:
                record_episode_sync_telemetry(
                    uow=telemetry_uow,
                    run=sync_run,
                    tool_types=sync_tool_types,
                )
    except Exception:
        return
