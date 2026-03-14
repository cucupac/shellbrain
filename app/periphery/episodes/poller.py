"""Repo-local background loop for episodic transcript sync."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from pathlib import Path

from app.boot.use_cases import get_uow_factory
from app.core.use_cases.sync_episode import sync_episode_from_host
from app.periphery.episodes.source_discovery import (
    SUPPORTED_HOSTS,
    default_search_roots,
    discover_active_host_session,
    resolve_host_transcript_source,
)


POLL_INTERVAL_SECONDS = 5
IDLE_EXIT_SECONDS = 15 * 60


@dataclass
class _HostState:
    """In-memory state for one tracked host while the poller is alive."""

    session_key: str
    transcript_path: Path
    last_mtime: float


def main() -> int:
    """Run the repo-local background episode sync loop."""

    parser = argparse.ArgumentParser(prog="memory-episode-poller")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()

    run_episode_poller(repo_id=args.repo_id, repo_root=Path(args.repo_root))
    return 0


def run_episode_poller(*, repo_id: str, repo_root: Path) -> None:
    """Run until the repo appears idle for long enough."""

    repo_root = repo_root.resolve()
    known_state: dict[str, _HostState] = {}
    last_change_at = time.monotonic()
    uow_factory = get_uow_factory()

    while True:
        saw_change = False
        for host_app in SUPPORTED_HOSTS:
            search_roots = default_search_roots(repo_root=repo_root, host_app=host_app)
            candidate = discover_active_host_session(
                host_app=host_app,
                repo_root=repo_root,
                search_roots=search_roots,
            )

            if candidate is None:
                if host_app in known_state:
                    _record_missing_source(
                        repo_root=repo_root,
                        host_app=host_app,
                        host_session_key=known_state[host_app].session_key,
                        search_roots=search_roots,
                        last_known_path=known_state[host_app].transcript_path,
                    )
                continue

            transcript_path = Path(candidate["transcript_path"])
            state = known_state.get(host_app)
            session_changed = state is not None and state.session_key != candidate["host_session_key"]
            if session_changed:
                _close_episode(
                    repo_id=repo_id,
                    host_app=host_app,
                    host_session_key=state.session_key,
                    uow_factory=uow_factory,
                )

            mtime = transcript_path.stat().st_mtime if transcript_path.exists() else 0.0
            should_sync = state is None or session_changed or state.last_mtime != mtime
            known_state[host_app] = _HostState(
                session_key=str(candidate["host_session_key"]),
                transcript_path=transcript_path,
                last_mtime=mtime,
            )
            if not should_sync:
                continue

            try:
                with uow_factory() as uow:
                    sync_episode_from_host(
                        repo_id=repo_id,
                        host_app=host_app,
                        host_session_key=str(candidate["host_session_key"]),
                        uow=uow,
                        search_roots=search_roots,
                        last_known_path=transcript_path,
                    )
                _record_status(
                    repo_root=repo_root,
                    host_app=host_app,
                    host_session_key=str(candidate["host_session_key"]),
                    last_successful_sync_at=_utc_now().isoformat(),
                    last_error=None,
                )
                saw_change = True
            except FileNotFoundError as exc:
                _record_status(
                    repo_root=repo_root,
                    host_app=host_app,
                    host_session_key=str(candidate["host_session_key"]),
                    last_successful_sync_at=None,
                    last_error=str(exc),
                )

        if saw_change:
            last_change_at = time.monotonic()
        elif time.monotonic() - last_change_at >= IDLE_EXIT_SECONDS:
            break

        time.sleep(POLL_INTERVAL_SECONDS)
def _close_episode(*, repo_id: str, host_app: str, host_session_key: str, uow_factory) -> None:
    """Close one active episode when a newer session replaces it."""

    canonical_thread_id = f"{host_app}:{host_session_key}"
    with uow_factory() as uow:
        episode = uow.episodes.get_episode_by_thread(repo_id=repo_id, thread_id=canonical_thread_id)
        if episode is None:
            return
        uow.episodes.close_episode(episode_id=episode.id, ended_at=_utc_now())


def _record_missing_source(
    *,
    repo_root: Path,
    host_app: str,
    host_session_key: str,
    search_roots: list[Path],
    last_known_path: Path,
) -> None:
    """Persist a clear health record when one previously-known source disappears."""

    try:
        resolve_host_transcript_source(
            host_app=host_app,
            host_session_key=host_session_key,
            search_roots=search_roots,
            last_known_path=last_known_path,
        )
    except FileNotFoundError as exc:
        _record_status(
            repo_root=repo_root,
            host_app=host_app,
            host_session_key=host_session_key,
            last_successful_sync_at=None,
            last_error=str(exc),
        )


def _record_status(
    *,
    repo_root: Path,
    host_app: str,
    host_session_key: str,
    last_successful_sync_at: str | None,
    last_error: str | None,
) -> None:
    """Write one small repo-local health/status file."""

    runtime_dir = repo_root / ".memory"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    status_path = runtime_dir / "episode_sync_status.json"
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        status = {"repo_root": str(repo_root), "hosts": {}}

    hosts = status.setdefault("hosts", {})
    host_status = hosts.setdefault(host_app, {})
    host_status["current_session_key"] = host_session_key
    if last_successful_sync_at is not None:
        host_status["last_successful_sync_at"] = last_successful_sync_at
    host_status["last_error"] = last_error
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")


def _utc_now() -> datetime:
    """Return a timezone-aware current UTC time."""

    return datetime.now(timezone.utc)


if __name__ == "__main__":
    raise SystemExit(main())
