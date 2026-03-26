"""Repo-local background loop for episodic transcript sync."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import time
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.boot.use_cases import get_uow_factory
from app.core.use_cases.record_episode_sync_telemetry import record_episode_sync_telemetry
from app.core.use_cases.sync_episode import sync_episode_from_host
from app.periphery.episodes.poller_lock import acquire_poller_lock, write_poller_pid_artifact
from app.periphery.episodes.source_discovery import (
    SUPPORTED_HOSTS,
    default_search_roots,
    discover_active_host_session,
    resolve_host_transcript_source,
)
from app.periphery.telemetry.sync_summary import build_episode_sync_records


POLL_INTERVAL_SECONDS = 5
IDLE_EXIT_SECONDS = 15 * 60


@dataclass
class _HostState:
    """In-shellbrain state for one tracked host while the poller is alive."""

    session_key: str
    transcript_path: Path
    last_freshness: float


def main() -> int:
    """Run the repo-local background episode sync loop."""

    parser = argparse.ArgumentParser(prog="shellbrain-episode-poller")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()

    run_episode_poller(repo_id=args.repo_id, repo_root=Path(args.repo_root))
    return 0


def run_episode_poller(*, repo_id: str, repo_root: Path) -> None:
    """Run until the repo appears idle for long enough."""

    repo_root = repo_root.resolve()
    lock_handle = acquire_poller_lock(repo_id=repo_id, repo_root=repo_root)
    if lock_handle is None:
        return

    known_state: dict[str, _HostState] = {}
    last_change_at = time.monotonic()
    uow_factory = get_uow_factory()
    try:
        _write_pid_artifact(repo_root=repo_root)
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

                freshness = float(candidate.get("updated_at") or 0.0)
                should_sync = state is None or session_changed or state.last_freshness != freshness
                known_state[host_app] = _HostState(
                    session_key=str(candidate["host_session_key"]),
                    transcript_path=transcript_path,
                    last_freshness=freshness,
                )
                if not should_sync:
                    continue

                sync_started_at = perf_counter()
                try:
                    with uow_factory() as uow:
                        sync_result = sync_episode_from_host(
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
                    _record_sync_telemetry_best_effort(
                        uow_factory=uow_factory,
                        repo_id=repo_id,
                        host_app=host_app,
                        host_session_key=str(candidate["host_session_key"]),
                        thread_id=str(sync_result["thread_id"]),
                        episode_id=str(sync_result["episode_id"]),
                        transcript_path=str(sync_result["transcript_path"]),
                        outcome="ok",
                        error_stage=None,
                        error_message=None,
                        duration_ms=int((perf_counter() - sync_started_at) * 1000),
                        imported_event_count=int(sync_result["imported_event_count"]),
                        total_event_count=int(sync_result["total_event_count"]),
                        user_event_count=int(sync_result["user_event_count"]),
                        assistant_event_count=int(sync_result["assistant_event_count"]),
                        tool_event_count=int(sync_result["tool_event_count"]),
                        system_event_count=int(sync_result["system_event_count"]),
                        tool_type_counts=dict(sync_result["tool_type_counts"]),
                    )
                    saw_change = True
                except Exception as exc:
                    _record_status(
                        repo_root=repo_root,
                        host_app=host_app,
                        host_session_key=str(candidate["host_session_key"]),
                        last_successful_sync_at=None,
                        last_error=str(exc),
                    )
                    _record_sync_telemetry_best_effort(
                        uow_factory=uow_factory,
                        repo_id=repo_id,
                        host_app=host_app,
                        host_session_key=str(candidate["host_session_key"]),
                        thread_id=f"{host_app}:{candidate['host_session_key']}",
                        episode_id=None,
                        transcript_path=str(transcript_path),
                        outcome="error",
                        error_stage="sync",
                        error_message=str(exc),
                        duration_ms=int((perf_counter() - sync_started_at) * 1000),
                        imported_event_count=0,
                        total_event_count=0,
                        user_event_count=0,
                        assistant_event_count=0,
                        tool_event_count=0,
                        system_event_count=0,
                        tool_type_counts={},
                    )

            if saw_change:
                last_change_at = time.monotonic()
            elif time.monotonic() - last_change_at >= IDLE_EXIT_SECONDS:
                break

            time.sleep(POLL_INTERVAL_SECONDS)
    finally:
        lock_handle.release()


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

    runtime_dir = repo_root / ".shellbrain"
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


def _write_pid_artifact(*, repo_root: Path) -> None:
    """Persist the compatibility pid artifact for the current poller process."""

    write_poller_pid_artifact(repo_root=repo_root)


def _utc_now() -> datetime:
    """Return a timezone-aware current UTC time."""

    return datetime.now(timezone.utc)


def _record_sync_telemetry_best_effort(
    *,
    uow_factory,
    repo_id: str,
    host_app: str,
    host_session_key: str,
    thread_id: str,
    episode_id: str | None,
    transcript_path: str | None,
    outcome: str,
    error_stage: str | None,
    error_message: str | None,
    duration_ms: int,
    imported_event_count: int,
    total_event_count: int,
    user_event_count: int,
    assistant_event_count: int,
    tool_event_count: int,
    system_event_count: int,
    tool_type_counts: dict[str, int],
) -> None:
    """Persist one poller sync-run row without affecting the poller loop."""

    try:
        run, tool_types = build_episode_sync_records(
            sync_run_id=str(uuid4()),
            source="poller",
            invocation_id=None,
            repo_id=repo_id,
            host_app=host_app,
            host_session_key=host_session_key,
            thread_id=thread_id,
            episode_id=episode_id,
            transcript_path=transcript_path,
            outcome=outcome,
            error_stage=error_stage,
            error_message=error_message,
            duration_ms=duration_ms,
            imported_event_count=imported_event_count,
            total_event_count=total_event_count,
            user_event_count=user_event_count,
            assistant_event_count=assistant_event_count,
            tool_event_count=tool_event_count,
            system_event_count=system_event_count,
            tool_type_counts=tool_type_counts,
        )
        with uow_factory() as uow:
            record_episode_sync_telemetry(uow=uow, run=run, tool_types=tool_types)
    except Exception:
        return


if __name__ == "__main__":
    raise SystemExit(main())
