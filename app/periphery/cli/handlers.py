"""This module defines CLI command handlers that dispatch to core use-case functions."""

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.boot.create_policy import get_create_hydration_defaults, get_create_policy_settings, validate_create_policy_settings
from app.boot.read_policy import get_read_hydration_defaults
from app.boot.update_policy import get_update_policy_settings, validate_update_policy_settings
from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.concepts import ConceptCommandRequest
from app.core.contracts.requests import (
    MemoryBatchUpdateRequest,
    MemoryCreateRequest,
    MemoryUpdateRequest,
)
from app.core.contracts.responses import OperationResult
from app.core.entities.identity import CallerIdentity, IdentityTrustLevel
from app.core.entities.telemetry import OperationDispatchTelemetryContext, SessionSelectionSummary
from app.core.use_cases.build_guidance import build_pending_utility_guidance
from app.core.use_cases.manage_session_state import SessionStateManager
from app.core.use_cases.create_memory import execute_create_memory
from app.core.use_cases.manage_concepts import execute_concept_command
from app.core.use_cases.recall_memory import execute_recall_memory
from app.core.use_cases.read_memory import execute_read_memory
from app.core.use_cases.record_episode_sync_telemetry import record_episode_sync_telemetry
from app.core.use_cases.record_model_usage_telemetry import record_model_usage_telemetry
from app.core.use_cases.record_operation_telemetry import record_operation_telemetry
from app.core.use_cases.sync_episode import sync_episode
from app.core.use_cases.update_memory import execute_update_memory
from app.periphery.cli.hydration import (
    hydrate_create_payload,
    hydrate_concept_payload,
    hydrate_events_payload,
    hydrate_read_payload,
    hydrate_update_payload,
)
from app.periphery.cli.schema_validation import (
    validate_create_schema,
    validate_concept_schema,
    validate_events_schema,
    validate_internal_create_contract,
    validate_internal_events_contract,
    validate_internal_recall_contract,
    validate_internal_read_contract,
    validate_internal_update_contract,
    validate_read_schema,
    validate_recall_schema,
    validate_update_schema,
)
from app.periphery.episodes.normalization import normalize_host_transcript
from app.periphery.episodes.model_usage import collect_model_usage_records_for_session
from app.periphery.identity.resolver import (
    discover_untrusted_events_candidate,
    resolve_caller_identity,
    resolve_trusted_events_source,
)
from app.periphery.session_state.file_store import FileSessionStateStore
from app.periphery.telemetry import get_operation_telemetry_context
from app.periphery.telemetry.operation_summary import (
    build_operation_invocation_record,
    build_recall_summary_records,
    build_read_summary_records,
    build_write_summary_records,
    infer_error_stage_from_errors,
)
from app.periphery.telemetry.session_selection import summarize_runtime_selection
from app.periphery.telemetry.sync_summary import build_episode_sync_records
from app.periphery.validation.integrity_validation import validate_create_integrity, validate_update_integrity
from app.periphery.validation.semantic_validation import validate_create_semantics, validate_update_semantics


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


def _validate_update_request(request: MemoryUpdateRequest | MemoryBatchUpdateRequest, *, uow, gates: list[str]) -> list[ErrorDetail]:
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
    repo_root: Path | None = None,
):
    """This function validates and dispatches a create payload to the create use-case."""

    started_at = perf_counter()
    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_telemetry_context = _ensure_telemetry_context(telemetry_context=telemetry_context, repo_root=resolved_repo_root)
    session_manager = SessionStateManager(store=FileSessionStateStore())
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
                                guidance = _build_guidance_payloads(
                                    uow_factory=uow_factory,
                                    repo_id=inferred_repo_id,
                                    caller_identity=resolved_telemetry_context.caller_identity,
                                    session_state=session_state,
                                    strong=strong_guidance,
                                )
                                if guidance:
                                    _attach_guidance(result, guidance)
                                    if session_state is not None and session_state.current_problem_id is not None:
                                        session_manager.record_guidance(
                                            repo_root=resolved_repo_root,
                                            caller_identity=resolved_telemetry_context.caller_identity,
                                            problem_id=session_state.current_problem_id,
                                        )
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


def handle_concept(
    payload: dict,
    *,
    uow_factory,
    inferred_repo_id: str,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    """Validate and dispatch a concept endpoint payload."""

    started_at = perf_counter()
    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_telemetry_context = _ensure_telemetry_context(telemetry_context=telemetry_context, repo_root=resolved_repo_root)
    request: ConceptCommandRequest | None = None
    result: dict | None = None
    error_stage: str | None = None
    try:
        hydrated_payload = hydrate_concept_payload(payload, inferred_repo_id=inferred_repo_id)
        request, errors = validate_concept_schema(hydrated_payload)
        if errors:
            error_stage = infer_error_stage_from_errors(_dump_errors(errors), default_stage="schema_validation")
            result = _error_response(errors)
        else:
            assert request is not None
            with uow_factory() as uow:
                result = execute_concept_command(request, uow).model_dump(mode="python")
    except ValueError as exc:
        error_stage = "semantic_validation"
        result = _error_response([ErrorDetail(code=ErrorCode.SEMANTIC_ERROR, message=str(exc))])
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])

    assert result is not None
    _persist_operation_telemetry_best_effort(
        command="concept",
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
    repo_root: Path | None = None,
):
    """This function validates and dispatches a read payload to the read use-case."""

    started_at = perf_counter()
    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_telemetry_context = _ensure_telemetry_context(telemetry_context=telemetry_context, repo_root=resolved_repo_root)
    session_manager = SessionStateManager(store=FileSessionStateStore())
    session_manager.load_active_state(
        repo_root=resolved_repo_root,
        caller_identity=resolved_telemetry_context.caller_identity,
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


def handle_recall(
    payload: dict,
    *,
    uow_factory,
    inferred_repo_id: str,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    """Validate and dispatch a minimal read-only recall payload."""

    started_at = perf_counter()
    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_telemetry_context = _ensure_telemetry_context(telemetry_context=telemetry_context, repo_root=resolved_repo_root)
    session_manager = SessionStateManager(store=FileSessionStateStore())
    session_manager.load_active_state(
        repo_root=resolved_repo_root,
        caller_identity=resolved_telemetry_context.caller_identity,
    )
    request = None
    result: dict | None = None
    recall_telemetry: dict | None = None
    error_stage: str | None = None
    try:
        agent_request, errors = validate_recall_schema(payload)
        if errors:
            error_stage = infer_error_stage_from_errors(_dump_errors(errors), default_stage="schema_validation")
            result = _error_response(errors)
        else:
            assert agent_request is not None
            hydrated_payload = agent_request.model_dump(mode="python", exclude_none=True)
            hydrated_payload.setdefault("op", "recall")
            hydrated_payload.setdefault("repo_id", inferred_repo_id)
            request, contract_errors = validate_internal_recall_contract(hydrated_payload)
            if contract_errors:
                error_stage = infer_error_stage_from_errors(
                    _dump_errors(contract_errors),
                    default_stage="contract_validation",
                )
                result = _error_response(contract_errors)
            else:
                assert request is not None
                with uow_factory() as uow:
                    result = execute_recall_memory(request, uow).model_dump(mode="python")
                data = result.get("data")
                if isinstance(data, dict):
                    telemetry_payload = data.pop("_telemetry", None)
                    if isinstance(telemetry_payload, dict):
                        recall_telemetry = telemetry_payload
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        error_stage = "internal_error"
        result = _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])

    assert result is not None
    _persist_operation_telemetry_best_effort(
        command="recall",
        uow_factory=uow_factory,
        repo_id=inferred_repo_id,
        telemetry_context=resolved_telemetry_context,
        result=result,
        error_stage=error_stage,
        request=request,
        agent_payload=payload,
        recall_telemetry=recall_telemetry,
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
    session_manager = SessionStateManager(store=FileSessionStateStore())
    request = None
    result: dict | None = None
    error_stage: str | None = None
    selection_summary = SessionSelectionSummary()
    sync_run = None
    sync_tool_types = ()
    model_usage_records = ()
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
                source = _resolve_events_source(
                    repo_root=resolved_repo_root,
                    search_roots_by_host=search_roots_by_host,
                    runtime_context=resolved_telemetry_context,
                )
                selection_summary = _selection_summary_from_events_source(source)
                sync_started_at = perf_counter()
                try:
                    normalized_events = normalize_host_transcript(
                        host_app=str(source.host_app),
                        host_session_key=str(source.host_session_key),
                        transcript_path=Path(str(source.transcript_path)),
                    )
                    with uow_factory() as uow:
                        sync_result = sync_episode(
                            repo_id=request.repo_id,
                            host_app=str(source.host_app),
                            host_session_key=str(source.host_session_key),
                            thread_id=str(source.canonical_thread_id),
                            transcript_path=str(source.transcript_path),
                            normalized_events=normalized_events,
                            uow=uow,
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
                                "host_app": source.host_app,
                                "thread_id": sync_result["thread_id"],
                                "events": [_serialize_episode_event(event) for event in events],
                            },
                        ).model_dump(mode="python")
                    selection_summary = replace(selection_summary, selected_episode_id=str(sync_result["episode_id"]))
                    if source.trusted:
                        session_manager.record_events(
                            repo_root=resolved_repo_root,
                            caller_identity=resolved_telemetry_context.caller_identity,
                            episode_id=str(sync_result["episode_id"]),
                            event_ids=[str(event["id"]) for event in result["data"]["events"]],
                        )
                    sync_run, sync_tool_types = build_episode_sync_records(
                        sync_run_id=str(uuid4()),
                        source="events_inline",
                        invocation_id=resolved_telemetry_context.invocation_id,
                        repo_id=request.repo_id,
                        host_app=str(source.host_app),
                        host_session_key=str(source.host_session_key),
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
                    try:
                        model_usage_records = tuple(
                            collect_model_usage_records_for_session(
                                repo_id=request.repo_id,
                                host_app=str(source.host_app),
                                host_session_key=str(source.host_session_key),
                                thread_id=str(sync_result["thread_id"]),
                                episode_id=str(sync_result["episode_id"]),
                                transcript_path=Path(str(sync_result["transcript_path"])),
                            )
                        )
                    except Exception:
                        model_usage_records = ()
                except Exception as exc:
                    error_stage = "sync"
                    result = _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])
                    sync_run, sync_tool_types = build_episode_sync_records(
                        sync_run_id=str(uuid4()),
                        source="events_inline",
                        invocation_id=resolved_telemetry_context.invocation_id,
                        repo_id=request.repo_id,
                        host_app=str(source.host_app),
                        host_session_key=str(source.host_session_key),
                        thread_id=selection_summary.selected_thread_id or str(source.canonical_thread_id),
                        episode_id=selection_summary.selected_episode_id,
                        transcript_path=str(source.transcript_path),
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
        model_usage_records=model_usage_records,
        total_latency_ms=int((perf_counter() - started_at) * 1000),
    )
    return result


def handle_update(
    payload: dict,
    *,
    uow_factory,
    inferred_repo_id: str,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    """This function validates and dispatches an update payload to the update use-case."""

    started_at = perf_counter()
    resolved_repo_root = (repo_root or Path.cwd()).resolve()
    resolved_telemetry_context = _ensure_telemetry_context(telemetry_context=telemetry_context, repo_root=resolved_repo_root)
    session_manager = SessionStateManager(store=FileSessionStateStore())
    session_state = session_manager.load_active_state(
        repo_root=resolved_repo_root,
        caller_identity=resolved_telemetry_context.caller_identity,
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
                    request, hydration_errors = _hydrate_update_request_evidence_from_session_state(
                        request=request,
                        session_state=session_state,
                    )
                    if hydration_errors:
                        error_stage = infer_error_stage_from_errors(
                            _dump_errors(hydration_errors),
                            default_stage="semantic_validation",
                        )
                        result = _error_response(hydration_errors)
                        request = None
                        raise _ReturnHandledError()
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
                            guidance = _build_guidance_payloads(
                                uow_factory=uow_factory,
                                repo_id=inferred_repo_id,
                                caller_identity=resolved_telemetry_context.caller_identity,
                                session_state=session_state,
                                strong=False,
                            )
                            if guidance:
                                _attach_guidance(result, guidance)
                                if session_state is not None and session_state.current_problem_id is not None:
                                    session_manager.record_guidance(
                                        repo_root=resolved_repo_root,
                                        caller_identity=resolved_telemetry_context.caller_identity,
                                        problem_id=session_state.current_problem_id,
                                    )
    except _ReturnHandledError:
        pass
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


class _ReturnHandledError(Exception):
    """Internal control-flow exception for already-materialized responses."""


def _resolve_events_source(
    *,
    repo_root: Path,
    search_roots_by_host: dict[str, list[Path]] | None,
    runtime_context: OperationDispatchTelemetryContext,
):
    """Resolve the exact trusted events source or an untrusted fallback candidate."""

    caller_identity = runtime_context.caller_identity
    if runtime_context.caller_identity_error is not None:
        raise _EventsSelectionError(runtime_context.caller_identity_error)

    if caller_identity is not None and caller_identity.trust_level == IdentityTrustLevel.TRUSTED:
        source = resolve_trusted_events_source(
            caller_identity=caller_identity,
            repo_root=repo_root,
            search_roots_by_host=search_roots_by_host,
        )
        if source.error is not None:
            raise _EventsSelectionError(source.error)
        return source

    fallback = discover_untrusted_events_candidate(
        repo_root=repo_root,
        search_roots_by_host=search_roots_by_host,
    )
    if fallback is None:
        raise _EventsSelectionError(
            ErrorDetail(
                code=ErrorCode.NOT_FOUND,
                message="No active host session found for this repo",
            )
        )
    return fallback


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
    caller_identity_resolution = resolve_caller_identity()
    return OperationDispatchTelemetryContext(
        invocation_id=str(uuid4()),
        repo_root=str((repo_root or Path.cwd()).resolve()),
        no_sync=False,
        caller_identity=caller_identity_resolution.caller_identity,
        caller_identity_error=caller_identity_resolution.error,
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
    model_usage_records=(),
    recall_telemetry: dict | None = None,
    total_latency_ms: int | None = None,
) -> None:
    """Persist invocation telemetry in a second best-effort transaction."""

    try:
        with uow_factory() as telemetry_uow:
            resolved_selection = selection_summary
            if resolved_selection is None:
                resolved_selection = _selection_summary_from_runtime_context(
                    caller_identity=telemetry_context.caller_identity,
                    repo_id=repo_id,
                    repo_root=Path(telemetry_context.repo_root),
                    uow=telemetry_uow,
                )
            invocation = build_operation_invocation_record(
                command=command,
                repo_id=repo_id,
                runtime_context=telemetry_context,
                selection_summary=resolved_selection,
                result=result,
                error_stage=error_stage,
                total_latency_ms=total_latency_ms if total_latency_ms is not None else 0,
            )

            read_summary = None
            read_items = ()
            recall_summary = None
            recall_items = ()
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

            if result.get("status") == "ok" and command == "recall" and request is not None:
                data = result.get("data", {})
                if isinstance(data, dict) and isinstance(recall_telemetry, dict):
                    brief = data.get("brief", {})
                    if isinstance(brief, dict):
                        fallback_reason = data.get("fallback_reason")
                        recall_summary, recall_items = build_recall_summary_records(
                            invocation_id=telemetry_context.invocation_id,
                            request=request,
                            recall_telemetry=recall_telemetry,
                            brief=brief,
                            fallback_reason=str(fallback_reason) if isinstance(fallback_reason, str) else None,
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
                recall_summary=recall_summary,
                recall_items=recall_items,
                write_summary=write_summary,
                write_items=write_items,
            )
            if sync_run is not None:
                record_episode_sync_telemetry(
                    uow=telemetry_uow,
                    run=sync_run,
                    tool_types=sync_tool_types,
                )
            if model_usage_records:
                record_model_usage_telemetry(
                    uow=telemetry_uow,
                    records=tuple(model_usage_records),
                )
    except Exception:
        return


def _selection_summary_from_events_source(source) -> SessionSelectionSummary:
    """Build telemetry selection summary from one resolved events source."""

    return SessionSelectionSummary(
        selected_host_app=source.host_app,
        selected_host_session_key=source.host_session_key,
        selected_thread_id=source.canonical_thread_id,
        matching_candidate_count=source.matching_candidate_count,
        selection_ambiguous=source.selection_ambiguous,
    )


def _selection_summary_from_runtime_context(*, caller_identity: CallerIdentity | None, repo_id: str, repo_root: Path, uow) -> SessionSelectionSummary:
    """Build lightweight non-events selection summary from trusted caller identity when present."""

    if caller_identity is None or caller_identity.trust_level != IdentityTrustLevel.TRUSTED:
        return summarize_runtime_selection(repo_root=repo_root, repo_id=repo_id, uow=uow)
    selected_episode_id = None
    episode = uow.episodes.get_episode_by_thread(repo_id=repo_id, thread_id=caller_identity.canonical_id or "")
    if episode is not None:
        selected_episode_id = episode.id
    return SessionSelectionSummary(
        selected_host_app=caller_identity.host_app,
        selected_host_session_key=caller_identity.host_session_key,
        selected_thread_id=caller_identity.canonical_id,
        selected_episode_id=selected_episode_id,
        matching_candidate_count=1,
        selection_ambiguous=False,
    )


def _build_guidance_payloads(*, uow_factory, repo_id: str, caller_identity: CallerIdentity | None, session_state, strong: bool) -> list[dict]:
    """Build public guidance payloads from telemetry and session state."""

    if session_state is None:
        return []
    with uow_factory() as guidance_uow:
        decisions = build_pending_utility_guidance(
            repo_id=repo_id,
            caller_identity=caller_identity,
            session_state=session_state,
            telemetry=guidance_uow.telemetry,
            now_iso=datetime.now(timezone.utc).isoformat(),
            strong=strong,
        )
    return [decision.to_payload() for decision in decisions]


def _attach_guidance(result: dict, guidance_payloads: list[dict]) -> None:
    """Attach one or more guidance payloads to a successful result."""

    data = result.setdefault("data", {})
    if not isinstance(data, dict):
        return
    data["guidance"] = guidance_payloads


def _hydrate_update_request_evidence_from_session_state(*, request, session_state):
    """Auto-fill missing utility evidence refs from session state when possible."""

    if session_state is None:
        if isinstance(request, MemoryBatchUpdateRequest):
            if any(item.update.evidence_refs for item in request.updates):
                return request, []
            return request, _missing_events_evidence_errors(request)
        if request.update.type != "utility_vote" or request.update.evidence_refs:
            return request, []
        return request, _missing_events_evidence_errors(request)

    if isinstance(request, MemoryBatchUpdateRequest):
        if any(item.update.evidence_refs for item in request.updates):
            return request, []
        if not session_state.last_events_event_ids:
            return request, _missing_events_evidence_errors(request)
        payload = request.model_dump(mode="python")
        for item in payload["updates"]:
            item["update"]["evidence_refs"] = list(session_state.last_events_event_ids)
        return MemoryBatchUpdateRequest.model_validate(payload), []

    if request.update.type != "utility_vote" or request.update.evidence_refs:
        return request, []
    if not session_state.last_events_event_ids:
        return request, _missing_events_evidence_errors(request)
    payload = request.model_dump(mode="python")
    payload["update"]["evidence_refs"] = list(session_state.last_events_event_ids)
    return MemoryUpdateRequest.model_validate(payload), []


def _missing_events_evidence_errors(request) -> list[ErrorDetail]:
    """Return the canonical semantic error when utility evidence cannot be auto-filled."""

    if isinstance(request, MemoryBatchUpdateRequest):
        return [
            ErrorDetail(
                code=ErrorCode.SEMANTIC_ERROR,
                message="Batch utility votes require recent episode evidence; run `events` first.",
                field="updates",
            )
        ]
    if getattr(request.update, "type", None) == "utility_vote":
        return [
            ErrorDetail(
                code=ErrorCode.SEMANTIC_ERROR,
                message="utility_vote requires recent episode evidence; run `events` first.",
                field="update.evidence_refs",
            )
        ]
    return []
