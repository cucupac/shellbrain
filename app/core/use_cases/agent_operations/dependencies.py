"""Dependency bundle for agent operation workflows."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from app.core.contracts.errors import ErrorDetail
from app.core.entities.settings import CreatePolicySettings, ReadPolicySettings, ThresholdSettings, UpdatePolicySettings
from app.core.entities.telemetry import OperationDispatchTelemetryContext, SessionSelectionSummary
from app.core.interfaces.clock import IClock
from app.core.interfaces.idgen import IIdGenerator
from app.core.interfaces.session_state_store import ISessionStateStore


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
    get_operation_telemetry_context: Callable[[], OperationDispatchTelemetryContext | None]
    resolve_caller_identity: Callable[[], object]
    resolve_trusted_events_source: Callable[..., object]
    discover_untrusted_events_candidate: Callable[..., object | None]
    normalize_host_transcript: Callable[..., list[dict]]
    collect_model_usage_records_for_session: Callable[..., Iterable[object]]
    summarize_runtime_selection: Callable[..., SessionSelectionSummary]
    create_policy_errors: tuple[ErrorDetail, ...] = field(default_factory=tuple)
    update_policy_errors: tuple[ErrorDetail, ...] = field(default_factory=tuple)
