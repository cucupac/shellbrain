"""Composition helpers for public operation command handlers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.core.errors import ErrorDetail
from app.core.entities.inner_agents import InnerAgentSettings
from app.core.entities.runtime_context import (
    OperationDispatchTelemetryContext,
    SessionSelectionSummary,
)
from app.core.entities.settings import (
    CreatePolicySettings,
    ReadPolicySettings,
    ThresholdSettings,
    UpdatePolicySettings,
)
from app.core.ports.host_apps.inner_agents import IInnerAgentRunner
from app.core.ports.local_state.session_state_store import ISessionStateStore
from app.core.ports.system.clock import IClock
from app.core.ports.system.idgen import IIdGenerator
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
from app.infrastructure.telemetry.sink import TelemetrySink
from app.startup.create_policy import (
    get_typed_create_policy_settings,
    validate_create_policy_settings,
)
from app.startup.internal_agents import (
    get_build_context_inner_agent_runner,
    get_build_context_settings,
)
from app.startup.read_policy import get_read_policy_settings
from app.startup.runtime_context import get_operation_telemetry_context
from app.startup.thresholds import get_typed_threshold_settings
from app.startup.update_policy import (
    get_typed_update_policy_settings,
    validate_update_policy_settings,
)


class OperationContextDependencies(Protocol):
    """Dependency subset needed to resolve one command telemetry context."""

    get_operation_telemetry_context: Callable[
        [], OperationDispatchTelemetryContext | None
    ]
    resolve_caller_identity: Callable[[], Any]
    id_generator: Any


class TelemetrySinkPort(Protocol):
    """Telemetry behavior supplied by startup without coupling CLI to storage."""

    def record(self, **kwargs: Any) -> None:
        """Persist one best-effort telemetry event."""


@dataclass(frozen=True)
class OperationDependencies:
    """Ports and settings injected by startup into operation workflows."""

    session_state_store: ISessionStateStore
    create_policy: CreatePolicySettings
    read_settings: ReadPolicySettings
    update_policy: UpdatePolicySettings
    threshold_settings: ThresholdSettings
    clock: IClock
    id_generator: IIdGenerator
    build_context_inner_agent_runner: IInnerAgentRunner | None
    build_context_settings: InnerAgentSettings
    get_operation_telemetry_context: Callable[
        [], OperationDispatchTelemetryContext | None
    ]
    resolve_caller_identity: Callable[[], object]
    resolve_trusted_events_source: Callable[..., object]
    discover_untrusted_events_candidate: Callable[..., object | None]
    normalize_host_transcript: Callable[..., list[dict]]
    collect_model_usage_records_for_session: Callable[..., Iterable[object]]
    summarize_runtime_selection: Callable[..., SessionSelectionSummary]
    telemetry_sink: TelemetrySinkPort
    create_policy_errors: tuple[ErrorDetail, ...] = field(default_factory=tuple)
    update_policy_errors: tuple[ErrorDetail, ...] = field(default_factory=tuple)


def ensure_telemetry_context(
    *,
    dependencies: OperationContextDependencies,
    telemetry_context: OperationDispatchTelemetryContext | None,
    repo_root: Path | None,
) -> OperationDispatchTelemetryContext:
    """Return the active handler telemetry context or synthesize one for direct calls."""

    if telemetry_context is not None:
        return telemetry_context
    inherited = dependencies.get_operation_telemetry_context()
    if inherited is not None:
        return inherited
    caller_identity_resolution = dependencies.resolve_caller_identity()
    return OperationDispatchTelemetryContext(
        invocation_id=dependencies.id_generator.new_id(),
        repo_root=str((repo_root or Path.cwd()).resolve()),
        no_sync=False,
        caller_identity=caller_identity_resolution.caller_identity,
        caller_identity_error=caller_identity_resolution.error,
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
        build_context_inner_agent_runner=get_build_context_inner_agent_runner(),
        build_context_settings=get_build_context_settings(),
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
