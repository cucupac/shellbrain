"""Host event source selection for agent operation workflows."""

from __future__ import annotations

from pathlib import Path

from app.core.errors import ErrorCode, ErrorDetail
from app.core.entities.identity import IdentityTrustLevel
from app.core.entities.runtime_context import (
    OperationDispatchTelemetryContext,
    SessionSelectionSummary,
)
from app.entrypoints.cli.handlers.dependencies import OperationDependencies


class EventsSelectionError(Exception):
    """Expected failure while resolving an events source."""

    def __init__(self, error: ErrorDetail) -> None:
        super().__init__(error.message)
        self.error = error


def resolve_events_source(
    *,
    dependencies: OperationDependencies,
    repo_root: Path,
    search_roots_by_host: dict[str, list[Path]] | None,
    runtime_context: OperationDispatchTelemetryContext,
):
    """Resolve the exact trusted events source or an untrusted fallback candidate."""

    caller_identity = runtime_context.caller_identity
    if runtime_context.caller_identity_error is not None:
        raise EventsSelectionError(runtime_context.caller_identity_error)

    if (
        caller_identity is not None
        and caller_identity.trust_level == IdentityTrustLevel.TRUSTED
    ):
        source = dependencies.resolve_trusted_events_source(
            caller_identity=caller_identity,
            repo_root=repo_root,
            search_roots_by_host=search_roots_by_host,
        )
        if source.error is not None:
            raise EventsSelectionError(source.error)
        return source

    fallback = dependencies.discover_untrusted_events_candidate(
        repo_root=repo_root,
        search_roots_by_host=search_roots_by_host,
    )
    if fallback is None:
        raise EventsSelectionError(
            ErrorDetail(
                code=ErrorCode.NOT_FOUND,
                message="No active host session found for this repo",
            )
        )
    return fallback


def selection_summary_from_events_source(source) -> SessionSelectionSummary:
    """Build telemetry selection summary from one resolved events source."""

    return SessionSelectionSummary(
        selected_host_app=source.host_app,
        selected_host_session_key=source.host_session_key,
        selected_thread_id=source.canonical_thread_id,
        matching_candidate_count=source.matching_candidate_count,
        selection_ambiguous=source.selection_ambiguous,
    )
