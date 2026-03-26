"""Helpers for resolving low-overhead telemetry session-selection summaries."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.core.entities.telemetry import SessionSelectionSummary
from app.periphery.episodes.claude_code import list_claude_code_sessions_for_repo
from app.periphery.episodes.codex import list_codex_sessions_for_repo
from app.periphery.episodes.cursor import list_cursor_sessions_for_repo
from app.periphery.episodes.source_discovery import SUPPORTED_HOSTS, default_search_roots


@dataclass(frozen=True)
class EventsDiscoveryCandidate:
    """Concrete host-session discovery result used by the events path."""

    host_app: str
    host_session_key: str
    transcript_path: Path
    search_roots: list[Path]
    summary: SessionSelectionSummary


def discover_events_candidate(
    *,
    repo_root: Path,
    search_roots_by_host: dict[str, list[Path]] | None = None,
) -> EventsDiscoveryCandidate | None:
    """Resolve the newest repo-matching host session across supported hosts."""

    discovered: list[tuple[str, dict[str, Any], list[Path]]] = []
    for host_app in SUPPORTED_HOSTS:
        search_roots = _search_roots_for_host(
            repo_root=repo_root,
            host_app=host_app,
            search_roots_by_host=search_roots_by_host,
        )
        candidates = _list_candidates_for_host(
            host_app=host_app,
            repo_root=repo_root,
            search_roots=search_roots,
        )
        for candidate in candidates:
            discovered.append((host_app, candidate, search_roots))

    if not discovered:
        return None

    host_app, candidate, search_roots = max(
        discovered,
        key=lambda item: (float(item[1]["updated_at"]), item[0]),
    )
    host_session_key = str(candidate["host_session_key"])
    summary = SessionSelectionSummary(
        selected_host_app=host_app,
        selected_host_session_key=host_session_key,
        selected_thread_id=f"{host_app}:{host_session_key}",
        matching_candidate_count=len(discovered),
        selection_ambiguous=len(discovered) > 1,
    )
    return EventsDiscoveryCandidate(
        host_app=host_app,
        host_session_key=host_session_key,
        transcript_path=Path(str(candidate["transcript_path"])),
        search_roots=search_roots,
        summary=summary,
    )


def read_runtime_session_status(repo_root: Path) -> dict[str, Any] | None:
    """Read the repo-local poller status file when it exists and is valid JSON."""

    status_path = repo_root / ".shellbrain" / "episode_sync_status.json"
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def summarize_runtime_selection(*, repo_root: Path, repo_id: str, uow=None) -> SessionSelectionSummary:
    """Resolve lightweight session context from the repo-local poller status file."""

    status = read_runtime_session_status(repo_root)
    if status is None:
        return SessionSelectionSummary()

    hosts = status.get("hosts")
    if not isinstance(hosts, dict):
        return SessionSelectionSummary()

    candidates: list[tuple[str, str, datetime]] = []
    for host_app, raw_host_status in hosts.items():
        if not isinstance(raw_host_status, dict):
            continue
        session_key = raw_host_status.get("current_session_key")
        if not isinstance(session_key, str) or not session_key:
            continue
        candidates.append((host_app, session_key, _parse_status_time(raw_host_status.get("last_successful_sync_at"))))

    if not candidates:
        return SessionSelectionSummary()

    host_app, session_key, _ = max(candidates, key=lambda item: (item[2], item[0]))
    summary = SessionSelectionSummary(
        selected_host_app=host_app,
        selected_host_session_key=session_key,
        selected_thread_id=f"{host_app}:{session_key}",
        matching_candidate_count=len(candidates),
        selection_ambiguous=len(candidates) > 1,
    )
    if uow is None:
        return summary

    episode = uow.episodes.get_episode_by_thread(repo_id=repo_id, thread_id=summary.selected_thread_id)
    if episode is None:
        return summary
    return replace(summary, selected_episode_id=episode.id)


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


def _list_candidates_for_host(*, host_app: str, repo_root: Path, search_roots: list[Path]) -> list[dict[str, Any]]:
    """List all repo-matching host sessions for one supported host."""

    if host_app == "codex":
        return list_codex_sessions_for_repo(repo_root=repo_root, search_roots=search_roots)
    if host_app == "claude_code":
        return list_claude_code_sessions_for_repo(repo_root=repo_root, search_roots=search_roots)
    if host_app == "cursor":
        return list_cursor_sessions_for_repo(repo_root=repo_root, search_roots=search_roots)
    raise ValueError(f"Unsupported host app for telemetry discovery: {host_app}")


def _parse_status_time(value: object) -> datetime:
    """Parse one poller status timestamp or return the minimum UTC instant."""

    if not isinstance(value, str) or not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
