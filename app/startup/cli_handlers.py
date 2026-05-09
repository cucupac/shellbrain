"""Composition helpers for public operation command handlers."""

from __future__ import annotations

from pathlib import Path

from app.core.contracts.concepts import ConceptAddRequest, ConceptUpdateRequest
from app.core.contracts.episodes import EpisodeEventsRequest
from app.core.contracts.errors import ErrorDetail
from app.core.contracts.memories import (
    MemoryBatchUpdateRequest,
    MemoryAddRequest,
    MemoryUpdateRequest,
)
from app.core.contracts.retrieval import MemoryReadRequest, MemoryRecallRequest
from app.core.entities.runtime_context import OperationDispatchTelemetryContext
from app.core.entities.settings import CreatePolicySettings, UpdatePolicySettings
from app.entrypoints.cli.handlers.internal_agent.concepts.add import run_concept_add_operation
from app.entrypoints.cli.handlers.internal_agent.concepts.update import (
    run_concept_update_operation,
)
from app.entrypoints.cli.handlers.command_context import OperationDependencies
from app.infrastructure.telemetry.sink import TelemetrySink
from app.entrypoints.cli.handlers.internal_agent.episodes.events import run_read_events_operation
from app.entrypoints.cli.handlers.internal_agent.memories.add import run_create_memory_operation
from app.entrypoints.cli.handlers.internal_agent.memories.update import (
    run_update_memory_operation,
)
from app.entrypoints.cli.handlers.internal_agent.retrieval.read import run_read_memory_operation
from app.entrypoints.cli.handlers.working_agent.recall import (
    run_recall_memory_operation,
)
from app.infrastructure.host_apps.identity.resolver import (
    discover_untrusted_events_candidate,
    resolve_caller_identity,
    resolve_trusted_events_source,
)
from app.infrastructure.host_apps.transcripts.model_usage import (
    collect_model_usage_records_for_session,
)
from app.infrastructure.host_apps.transcripts.normalization import normalize_host_transcript
from app.infrastructure.host_apps.transcripts.session_selection import (
    summarize_runtime_selection,
)
from app.infrastructure.local_state.session_state_file_store import (
    FileSessionStateStore,
)
from app.infrastructure.system.clock import SystemClock
from app.infrastructure.system.id_generator import UuidGenerator
from app.startup.create_policy import (
    get_typed_create_policy_settings,
    validate_create_policy_settings,
)
from app.startup.read_policy import get_read_policy_settings
from app.startup.runtime_context import get_operation_telemetry_context
from app.startup.thresholds import get_typed_threshold_settings
from app.startup.update_policy import (
    get_typed_update_policy_settings,
    validate_update_policy_settings,
)


def build_operation_dependencies() -> OperationDependencies:
    """Wire concrete runtime ports into core operation orchestration."""

    clock = SystemClock()
    return OperationDependencies(
        session_state_store=FileSessionStateStore(),
        create_policy=_load_create_policy_or_fallback(),
        read_settings=get_read_policy_settings(),
        update_policy=_load_update_policy_or_fallback(),
        threshold_settings=get_typed_threshold_settings(),
        clock=clock,
        id_generator=UuidGenerator(),
        get_operation_telemetry_context=get_operation_telemetry_context,
        resolve_caller_identity=resolve_caller_identity,
        resolve_trusted_events_source=resolve_trusted_events_source,
        discover_untrusted_events_candidate=discover_untrusted_events_candidate,
        normalize_host_transcript=normalize_host_transcript,
        collect_model_usage_records_for_session=collect_model_usage_records_for_session,
        summarize_runtime_selection=summarize_runtime_selection,
        telemetry_sink=TelemetrySink(
            clock=clock, summarize_runtime_selection=summarize_runtime_selection
        ),
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


def handle_memory_add(
    request: MemoryAddRequest | None,
    *,
    uow_factory,
    embedding_provider_factory,
    embedding_model: str,
    inferred_repo_id: str,
    validation_errors: tuple[ErrorDetail, ...] | list[ErrorDetail] = (),
    validation_error_stage: str = "schema_validation",
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    return run_create_memory_operation(
        request,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        embedding_provider_factory=embedding_provider_factory,
        embedding_model=embedding_model,
        inferred_repo_id=inferred_repo_id,
        validation_errors=validation_errors,
        validation_error_stage=validation_error_stage,
        telemetry_context=telemetry_context,
        repo_root=repo_root,
    )


def handle_concept_add(
    request: ConceptAddRequest | None,
    *,
    uow_factory,
    inferred_repo_id: str,
    validation_errors: tuple[ErrorDetail, ...] | list[ErrorDetail] = (),
    validation_error_stage: str = "schema_validation",
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    return run_concept_add_operation(
        request,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        validation_errors=validation_errors,
        validation_error_stage=validation_error_stage,
        telemetry_context=telemetry_context,
        repo_root=repo_root,
    )


def handle_concept_update(
    request: ConceptUpdateRequest | None,
    *,
    uow_factory,
    inferred_repo_id: str,
    validation_errors: tuple[ErrorDetail, ...] | list[ErrorDetail] = (),
    validation_error_stage: str = "schema_validation",
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    return run_concept_update_operation(
        request,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        validation_errors=validation_errors,
        validation_error_stage=validation_error_stage,
        telemetry_context=telemetry_context,
        repo_root=repo_root,
    )


def handle_read(
    request: MemoryReadRequest | None,
    *,
    uow_factory,
    inferred_repo_id: str,
    validation_errors: tuple[ErrorDetail, ...] | list[ErrorDetail] = (),
    validation_error_stage: str = "schema_validation",
    requested_limit: int | None = None,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    return run_read_memory_operation(
        request,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        validation_errors=validation_errors,
        validation_error_stage=validation_error_stage,
        requested_limit=requested_limit,
        telemetry_context=telemetry_context,
        repo_root=repo_root,
    )


def handle_recall(
    request: MemoryRecallRequest | None,
    *,
    uow_factory,
    inferred_repo_id: str,
    validation_errors: tuple[ErrorDetail, ...] | list[ErrorDetail] = (),
    validation_error_stage: str = "schema_validation",
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    return run_recall_memory_operation(
        request,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        validation_errors=validation_errors,
        validation_error_stage=validation_error_stage,
        telemetry_context=telemetry_context,
        repo_root=repo_root,
    )


def handle_events(
    request: EpisodeEventsRequest | None,
    *,
    uow_factory,
    inferred_repo_id: str,
    validation_errors: tuple[ErrorDetail, ...] | list[ErrorDetail] = (),
    validation_error_stage: str = "schema_validation",
    repo_root: Path | None = None,
    search_roots_by_host: dict[str, list[Path]] | None = None,
    telemetry_context: OperationDispatchTelemetryContext | None = None,
):
    return run_read_events_operation(
        request,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        validation_errors=validation_errors,
        validation_error_stage=validation_error_stage,
        repo_root=repo_root,
        search_roots_by_host=search_roots_by_host,
        telemetry_context=telemetry_context,
    )


def handle_update(
    request: MemoryUpdateRequest | MemoryBatchUpdateRequest | None,
    *,
    uow_factory,
    inferred_repo_id: str,
    validation_errors: tuple[ErrorDetail, ...] | list[ErrorDetail] = (),
    validation_error_stage: str = "schema_validation",
    telemetry_context: OperationDispatchTelemetryContext | None = None,
    repo_root: Path | None = None,
):
    return run_update_memory_operation(
        request,
        dependencies=build_operation_dependencies(),
        uow_factory=uow_factory,
        inferred_repo_id=inferred_repo_id,
        validation_errors=validation_errors,
        validation_error_stage=validation_error_stage,
        telemetry_context=telemetry_context,
        repo_root=repo_root,
    )
