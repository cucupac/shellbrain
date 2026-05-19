"""Entrypoint-owned dependency protocols for CLI operation handlers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
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


class OperationDependencies(Protocol):
    """Ports and settings consumed by operation handlers."""

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
    create_policy_errors: tuple[ErrorDetail, ...]
    update_policy_errors: tuple[ErrorDetail, ...]


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
