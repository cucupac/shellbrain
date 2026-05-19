"""Resolve caller identity and exact event sources across supported hosts."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from app.core.errors import ErrorDetail
from app.core.entities.identity import CallerIdentity, IdentityTrustLevel
from app.infrastructure.host_apps.transcripts.source_discovery import (
    SUPPORTED_HOSTS,
    default_search_roots,
)
from app.infrastructure.host_apps.identity.claude_runtime import (
    detect_claude_runtime_without_hook,
    resolve_trusted_claude_caller_identity,
    resolve_trusted_claude_transcript_path,
)
from app.infrastructure.host_apps.identity.codex_runtime import (
    resolve_codex_caller_identity,
    resolve_codex_transcript_for_caller,
)
from app.infrastructure.host_apps.identity.compatibility import (
    host_hook_missing_error,
    host_identity_drifted_error,
    host_identity_unsupported_error,
)
from app.infrastructure.host_apps.transcripts.session_selection import (
    discover_events_candidate,
)


@dataclass(frozen=True)
class CallerIdentityResolution:
    """Resolved caller identity plus any compatibility error and trusted path hint."""

    caller_identity: CallerIdentity | None
    transcript_path_hint: Path | None = None
    error: ErrorDetail | None = None


@dataclass(frozen=True)
class ResolvedEventsSource:
    """Resolved exact or fallback events source for one operation."""

    caller_identity: CallerIdentity | None
    host_app: str | None = None
    host_session_key: str | None = None
    canonical_thread_id: str | None = None
    transcript_path: Path | None = None
    search_roots: tuple[Path, ...] = ()
    matching_candidate_count: int = 0
    selection_ambiguous: bool = False
    trusted: bool = False
    error: ErrorDetail | None = None


def resolve_caller_identity() -> CallerIdentityResolution:
    """Resolve caller identity from trusted runtimes before falling back to none."""

    inner_agent_parent = _resolve_inner_agent_parent_identity()
    if inner_agent_parent is not None:
        return inner_agent_parent

    codex_identity = resolve_codex_caller_identity()
    if codex_identity is not None:
        return CallerIdentityResolution(caller_identity=codex_identity)

    claude_identity = resolve_trusted_claude_caller_identity()
    if claude_identity is not None:
        if claude_identity.trust_level == IdentityTrustLevel.UNSUPPORTED:
            return CallerIdentityResolution(
                caller_identity=None, error=host_identity_unsupported_error()
            )
        return CallerIdentityResolution(
            caller_identity=claude_identity,
            transcript_path_hint=resolve_trusted_claude_transcript_path(),
        )

    if detect_claude_runtime_without_hook():
        return CallerIdentityResolution(
            caller_identity=None, error=host_hook_missing_error()
        )
    return CallerIdentityResolution(caller_identity=None)


def _resolve_inner_agent_parent_identity() -> CallerIdentityResolution | None:
    """Resolve the outer caller identity inherited by a Codex inner agent."""

    if not os.getenv("SHELLBRAIN_INNER_AGENT_MODE"):
        return None
    host_app = os.getenv("SHELLBRAIN_PARENT_HOST_APP", "").strip()
    host_session_key = os.getenv("SHELLBRAIN_PARENT_HOST_SESSION_KEY", "").strip()
    if not host_app or not host_session_key:
        return None
    agent_key = os.getenv("SHELLBRAIN_PARENT_AGENT_KEY") or None
    try:
        caller_identity = CallerIdentity(
            host_app=host_app,
            host_session_key=host_session_key,
            agent_key=agent_key,
            trust_level=IdentityTrustLevel.TRUSTED,
        )
    except ValueError:
        return None
    transcript_path = os.getenv("SHELLBRAIN_PARENT_TRANSCRIPT_PATH", "").strip()
    return CallerIdentityResolution(
        caller_identity=caller_identity,
        transcript_path_hint=Path(transcript_path) if transcript_path else None,
    )


def resolve_trusted_events_source(
    *,
    caller_identity: CallerIdentity,
    repo_root: Path,
    search_roots_by_host: dict[str, list[Path]] | None = None,
) -> ResolvedEventsSource:
    """Resolve the exact transcript source for one trusted caller."""

    search_roots = _search_roots_for_host(
        repo_root=repo_root,
        host_app=caller_identity.host_app,
        search_roots_by_host=search_roots_by_host,
    )
    try:
        if caller_identity.host_app == "codex":
            transcript_path = resolve_codex_transcript_for_caller(
                caller_identity=caller_identity,
                search_roots=search_roots,
            )
        elif caller_identity.host_app == "claude_code":
            transcript_path = resolve_trusted_claude_transcript_path()
            if transcript_path is None:
                return ResolvedEventsSource(
                    caller_identity=caller_identity,
                    error=host_identity_drifted_error(
                        caller_id=caller_identity.canonical_id or ""
                    ),
                )
        else:
            return ResolvedEventsSource(
                caller_identity=caller_identity, error=host_identity_unsupported_error()
            )
    except FileNotFoundError:
        return ResolvedEventsSource(
            caller_identity=caller_identity,
            error=host_identity_drifted_error(
                caller_id=caller_identity.canonical_id or ""
            ),
        )

    return ResolvedEventsSource(
        caller_identity=caller_identity,
        host_app=caller_identity.host_app,
        host_session_key=caller_identity.host_session_key,
        canonical_thread_id=caller_identity.canonical_id,
        transcript_path=transcript_path,
        search_roots=tuple(search_roots),
        matching_candidate_count=1,
        selection_ambiguous=False,
        trusted=True,
    )


def discover_untrusted_events_candidate(
    *,
    repo_root: Path,
    search_roots_by_host: dict[str, list[Path]] | None = None,
) -> ResolvedEventsSource | None:
    """Discover the newest repo-matching host session as an untrusted fallback."""

    discovery = discover_events_candidate(
        repo_root=repo_root, search_roots_by_host=search_roots_by_host
    )
    if discovery is None:
        return None
    caller_identity = CallerIdentity(
        host_app=discovery.host_app,
        host_session_key=discovery.host_session_key,
        canonical_id=discovery.summary.selected_thread_id,
        trust_level=IdentityTrustLevel.UNTRUSTED,
    )
    return ResolvedEventsSource(
        caller_identity=caller_identity,
        host_app=discovery.host_app,
        host_session_key=discovery.host_session_key,
        canonical_thread_id=discovery.summary.selected_thread_id,
        transcript_path=discovery.transcript_path,
        search_roots=tuple(discovery.search_roots),
        matching_candidate_count=discovery.summary.matching_candidate_count,
        selection_ambiguous=discovery.summary.selection_ambiguous,
        trusted=False,
    )


def _search_roots_for_host(
    *,
    repo_root: Path,
    host_app: str,
    search_roots_by_host: dict[str, list[Path]] | None,
) -> list[Path]:
    """Resolve bounded search roots for one host with optional test overrides."""

    if search_roots_by_host is not None:
        return [Path(path) for path in search_roots_by_host.get(host_app, [])]
    if host_app not in SUPPORTED_HOSTS:
        return [repo_root]
    return default_search_roots(repo_root=repo_root, host_app=host_app)
