"""This module defines CLI command handlers that dispatch to core use-case functions."""

import json
from pathlib import Path

from app.boot.create_policy import get_create_hydration_defaults, get_create_policy_settings, validate_create_policy_settings
from app.boot.read_policy import get_read_hydration_defaults
from app.boot.update_policy import get_update_policy_settings, validate_update_policy_settings
from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.requests import EpisodeEventsRequest, MemoryCreateRequest, MemoryUpdateRequest
from app.core.contracts.responses import OperationResult
from app.core.use_cases.create_memory import execute_create_memory
from app.core.use_cases.read_memory import execute_read_memory
from app.core.use_cases.sync_episode import sync_episode_from_host
from app.core.use_cases.update_memory import execute_update_memory
from app.periphery.cli.hydration import (
    hydrate_create_payload,
    hydrate_events_payload,
    hydrate_read_payload,
    hydrate_update_payload,
)
from app.periphery.cli.schema_validation import (
    validate_create_schema,
    validate_events_schema,
    validate_internal_create_contract,
    validate_internal_events_contract,
    validate_internal_read_contract,
    validate_internal_update_contract,
    validate_read_schema,
    validate_update_schema,
)
from app.periphery.episodes.source_discovery import SUPPORTED_HOSTS, default_search_roots, discover_active_host_session
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
):
    """This function validates and dispatches a create payload to the create use-case."""

    policy_errors = validate_create_policy_settings()
    if policy_errors:
        return _error_response(policy_errors)
    policy = get_create_policy_settings()
    agent_request, errors = validate_create_schema(payload)
    if errors:
        return _error_response(errors)
    assert agent_request is not None
    resolved_defaults = defaults if defaults is not None else get_create_hydration_defaults()
    hydrated_payload = hydrate_create_payload(
        agent_request.model_dump(mode="python", exclude_none=True),
        inferred_repo_id=inferred_repo_id,
        defaults=resolved_defaults,
    )
    request, contract_errors = validate_internal_create_contract(hydrated_payload)
    if contract_errors:
        return _error_response(contract_errors)
    assert request is not None
    try:
        with uow_factory() as uow:
            validation_errors = _validate_create_request(request, uow=uow, gates=policy["gates"])
            if validation_errors:
                return _error_response(validation_errors)
            embedding_provider = embedding_provider_factory()
            return execute_create_memory(
                request,
                uow,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
            ).model_dump(mode="python")
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        return _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])


def handle_read(payload: dict, *, uow_factory, inferred_repo_id: str, defaults: dict | None = None):
    """This function validates and dispatches a read payload to the read use-case."""

    agent_request, errors = validate_read_schema(payload)
    if errors:
        return _error_response(errors)
    assert agent_request is not None
    resolved_defaults = defaults if defaults is not None else get_read_hydration_defaults()
    hydrated_payload = hydrate_read_payload(
        agent_request.model_dump(mode="python", exclude_none=True),
        inferred_repo_id=inferred_repo_id,
        defaults=resolved_defaults,
    )
    request, contract_errors = validate_internal_read_contract(hydrated_payload)
    if contract_errors:
        return _error_response(contract_errors)
    assert request is not None
    try:
        with uow_factory() as uow:
            return execute_read_memory(request, uow).model_dump(mode="python")
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        return _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])


def handle_events(
    payload: dict,
    *,
    uow_factory,
    inferred_repo_id: str,
    repo_root: Path | None = None,
    search_roots_by_host: dict[str, list[Path]] | None = None,
):
    """Validate and dispatch an events payload to the active-episode browsing flow."""

    agent_request, errors = validate_events_schema(payload)
    if errors:
        return _error_response(errors)
    assert agent_request is not None
    hydrated_payload = hydrate_events_payload(
        agent_request.model_dump(mode="python", exclude_none=True),
        inferred_repo_id=inferred_repo_id,
    )
    request, contract_errors = validate_internal_events_contract(hydrated_payload)
    if contract_errors:
        return _error_response(contract_errors)
    assert request is not None

    try:
        resolved_repo_root = (repo_root or Path.cwd()).resolve()
        selected_candidate, selected_search_roots, selected_host_app = _resolve_events_candidate(
            request,
            repo_root=resolved_repo_root,
            search_roots_by_host=search_roots_by_host,
        )
        with uow_factory() as uow:
            sync_episode_from_host(
                repo_id=request.repo_id,
                host_app=selected_host_app,
                host_session_key=str(selected_candidate["host_session_key"]),
                uow=uow,
                search_roots=selected_search_roots,
                last_known_path=Path(str(selected_candidate["transcript_path"])),
            )
            thread_id = f"{selected_host_app}:{selected_candidate['host_session_key']}"
            episode = uow.episodes.get_episode_by_thread(repo_id=request.repo_id, thread_id=thread_id)
            if episode is None:
                return _error_response(
                    [
                        ErrorDetail(
                            code=ErrorCode.NOT_FOUND,
                            message="Active episode could not be loaded after sync",
                        )
                    ]
                )
            events = uow.episodes.list_recent_events(
                repo_id=request.repo_id,
                episode_id=episode.id,
                limit=request.limit,
            )
            return OperationResult(
                status="ok",
                data={
                    "episode_id": episode.id,
                    "host_app": episode.host_app,
                    "thread_id": episode.thread_id,
                    "events": [_serialize_episode_event(event) for event in events],
                },
            ).model_dump(mode="python")
    except _EventsSelectionError as exc:
        return _error_response([exc.error])
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        return _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])


def handle_update(payload: dict, *, uow_factory, inferred_repo_id: str):
    """This function validates and dispatches an update payload to the update use-case."""

    policy_errors = validate_update_policy_settings()
    if policy_errors:
        return _error_response(policy_errors)
    policy = get_update_policy_settings()
    agent_request, errors = validate_update_schema(payload)
    if errors:
        return _error_response(errors)
    assert agent_request is not None
    hydrated_payload = hydrate_update_payload(
        agent_request.model_dump(mode="python", exclude_none=True),
        inferred_repo_id=inferred_repo_id,
    )
    request, contract_errors = validate_internal_update_contract(hydrated_payload)
    if contract_errors:
        return _error_response(contract_errors)
    assert request is not None
    try:
        with uow_factory() as uow:
            validation_errors = _validate_update_request(request, uow=uow, gates=policy["gates"])
            if validation_errors:
                return _error_response(validation_errors)
            return execute_update_memory(request, uow).model_dump(mode="python")
    except Exception as exc:  # pragma: no cover - defensive fallback envelope
        return _error_response([ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))])


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
) -> tuple[dict, list[Path], str]:
    """Resolve the newest active host session for an events request."""

    _ = request

    discovered: list[tuple[str, dict, list[Path]]] = []
    for host_app in SUPPORTED_HOSTS:
        search_roots = _search_roots_for_host(
            repo_root=repo_root,
            host_app=host_app,
            search_roots_by_host=search_roots_by_host,
        )
        candidate = discover_active_host_session(
            host_app=host_app,
            repo_root=repo_root,
            search_roots=search_roots,
        )
        if candidate is not None:
            discovered.append((host_app, candidate, search_roots))

    if not discovered:
        raise _EventsSelectionError(
            ErrorDetail(
                code=ErrorCode.NOT_FOUND,
                message="No active host session found for this repo",
            )
        )
    host_app, candidate, search_roots = max(
        discovered,
        key=lambda item: (float(item[1]["updated_at"]), item[0]),
    )
    return candidate, search_roots, host_app


def _search_roots_for_host(
    *,
    repo_root: Path,
    host_app: str,
    search_roots_by_host: dict[str, list[Path]] | None,
) -> list[Path]:
    """Resolve bounded search roots for one host with optional test overrides."""

    if search_roots_by_host is not None:
        return [Path(path) for path in search_roots_by_host.get(host_app, [])]
    return default_search_roots(repo_root=repo_root, host_app=host_app)


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
