"""Composition helpers for public operation command handlers."""

from __future__ import annotations

from pathlib import Path

from app.core.entities.telemetry import OperationDispatchTelemetryContext
from app.core.entities.settings import CreatePolicySettings, UpdatePolicySettings
from app.core.use_cases.operations.handlers import (
    OperationDependencies,
    handle_concept as _handle_concept,
    handle_create as _handle_create,
    handle_events as _handle_events,
    handle_read as _handle_read,
    handle_recall as _handle_recall,
    handle_update as _handle_update,
)
from app.periphery.host_identity.resolver import (
    discover_untrusted_events_candidate,
    resolve_caller_identity,
    resolve_trusted_events_source,
)
from app.periphery.host_transcripts.model_usage import collect_model_usage_records_for_session
from app.periphery.host_transcripts.normalization import normalize_host_transcript
from app.periphery.host_transcripts.session_selection import summarize_runtime_selection
from app.periphery.local_state.session_state_file_store import FileSessionStateStore
from app.startup.create_policy import get_typed_create_policy_settings, validate_create_policy_settings
from app.startup.read_policy import get_read_policy_settings
from app.startup.runtime_context import get_operation_telemetry_context
from app.startup.thresholds import get_typed_threshold_settings
from app.startup.update_policy import get_typed_update_policy_settings, validate_update_policy_settings


def build_operation_dependencies() -> OperationDependencies:
    """Wire concrete runtime ports into core operation orchestration."""

    return OperationDependencies(
        session_state_store=FileSessionStateStore(),
        create_policy=_load_create_policy_or_fallback(),
        read_settings=get_read_policy_settings(),
        update_policy=_load_update_policy_or_fallback(),
        threshold_settings=get_typed_threshold_settings(),
        get_operation_telemetry_context=get_operation_telemetry_context,
        resolve_caller_identity=resolve_caller_identity,
        resolve_trusted_events_source=resolve_trusted_events_source,
        discover_untrusted_events_candidate=discover_untrusted_events_candidate,
        normalize_host_transcript=normalize_host_transcript,
        collect_model_usage_records_for_session=collect_model_usage_records_for_session,
        summarize_runtime_selection=summarize_runtime_selection,
        create_policy_errors=tuple(validate_create_policy_settings()),
        update_policy_errors=tuple(validate_update_policy_settings()),
    )


def _load_create_policy_or_fallback() -> CreatePolicySettings:
    try:
        return get_typed_create_policy_settings()
    except ValueError:
        return CreatePolicySettings(gates=("schema",), defaults={"scope": "repo"})


def _load_update_policy_or_fallback() -> UpdatePolicySettings:
    try:
        return get_typed_update_policy_settings()
    except ValueError:
        return UpdatePolicySettings(gates=("schema",))


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
    return _handle_create(
        payload,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        embedding_provider_factory=embedding_provider_factory,
        embedding_model=embedding_model,
        inferred_repo_id=inferred_repo_id,
        defaults=defaults,
        telemetry_context=telemetry_context,
        repo_root=repo_root,
    )


def handle_concept(
    payload: dict,
    *,
    uow_factory,
    inferred_repo_id: str,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    return _handle_concept(
        payload,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        telemetry_context=telemetry_context,
        repo_root=repo_root,
    )


def handle_read(
    payload: dict,
    *,
    uow_factory,
    inferred_repo_id: str,
    defaults: dict | None = None,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    return _handle_read(
        payload,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        defaults=defaults,
        telemetry_context=telemetry_context,
        repo_root=repo_root,
    )


def handle_recall(
    payload: dict,
    *,
    uow_factory,
    inferred_repo_id: str,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    return _handle_recall(
        payload,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        telemetry_context=telemetry_context,
        repo_root=repo_root,
    )


def handle_events(
    payload: dict,
    *,
    uow_factory,
    inferred_repo_id: str,
    repo_root: Path | None = None,
    search_roots_by_host: dict[str, list[Path]] | None = None,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
):
    return _handle_events(
        payload,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        repo_root=repo_root,
        search_roots_by_host=search_roots_by_host,
        telemetry_context=telemetry_context,
    )


def handle_update(
    payload: dict,
    *,
    uow_factory,
    inferred_repo_id: str,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    return _handle_update(
        payload,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        telemetry_context=telemetry_context,
        repo_root=repo_root,
    )
