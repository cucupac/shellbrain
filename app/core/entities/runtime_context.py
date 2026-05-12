"""Per-invocation runtime context shared across CLI handlers."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import ErrorDetail
from app.core.entities.identity import CallerIdentity


@dataclass(frozen=True)
class RuntimeContext:
    """Per-command context captured in CLI main and consumed by handlers."""

    invocation_id: str
    repo_root: str
    no_sync: bool = False
    caller_identity: CallerIdentity | None = None
    caller_identity_error: ErrorDetail | None = None


OperationDispatchTelemetryContext = RuntimeContext


@dataclass(frozen=True)
class SessionSelectionSummary:
    """Resolved session/thread context recorded alongside one command invocation."""

    selected_host_app: str | None = None
    selected_host_session_key: str | None = None
    selected_thread_id: str | None = None
    selected_episode_id: str | None = None
    matching_candidate_count: int = 0
    selection_ambiguous: bool = False
