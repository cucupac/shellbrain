"""Repo-local background loop for episodic transcript sync."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import time
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from app.core.use_cases.episodes.close_replaced_episode import close_replaced_episode
from app.core.use_cases.episodes.sync_discovered_host_session import (
    sync_discovered_host_session,
)
from app.infrastructure.host_apps.transcripts.model_usage import (
    collect_model_usage_records_for_session,
)
from app.infrastructure.host_apps.transcripts.normalization import normalize_host_transcript
from app.infrastructure.host_apps.transcripts.source_discovery import (
    SUPPORTED_HOSTS,
    default_search_roots,
    discover_active_host_session,
    resolve_host_transcript_source,
)
from app.infrastructure.system.clock import SystemClock
from app.infrastructure.system.id_generator import UuidGenerator
from app.infrastructure.process.episode_sync.status_store import (
    record_episode_sync_status,
)
from app.infrastructure.telemetry.recorder import (
    record_episode_sync_telemetry,
    record_model_usage_telemetry,
)
from app.infrastructure.telemetry.sync_records import (
    build_episode_sync_records,
)
from app.infrastructure.process.episode_sync.lock_file import (
    acquire_poller_lock,
    write_poller_pid_artifact,
)


POLL_INTERVAL_SECONDS = 5
IDLE_EXIT_SECONDS = 15 * 60


@dataclass
class _HostState:
    """In-shellbrain state for one tracked host while the poller is alive."""

    session_key: str
    transcript_path: Path
    last_freshness: float


def sync_episode_from_host(
    *,
    repo_id: str,
    host_app: str,
    host_session_key: str,
    uow,
    search_roots,
    last_known_path=None,
) -> dict[str, object]:
    """Resolve and normalize one host transcript, then sync through core."""

    return sync_discovered_host_session(
        repo_id=repo_id,
        host_app=host_app,
        host_session_key=host_session_key,
        uow=uow,
        search_roots=search_roots,
        resolve_host_transcript_source=resolve_host_transcript_source,
        normalize_host_transcript=normalize_host_transcript,
        clock=SystemClock(),
        id_generator=UuidGenerator(),
        last_known_path=last_known_path,
    )


def run_episode_poller(*, repo_id: str, repo_root: Path, uow_factory) -> None:
    """Run until the repo appears idle for long enough."""

    repo_root = repo_root.resolve()
    lock_handle = acquire_poller_lock(repo_id=repo_id, repo_root=repo_root)
    if lock_handle is None:
        return

    known_state: dict[str, _HostState] = {}
    last_change_at = time.monotonic()
    try:
        _write_pid_artifact(repo_root=repo_root)
        while True:
            saw_change = False
            for host_app in SUPPORTED_HOSTS:
                search_roots = default_search_roots(
                    repo_root=repo_root, host_app=host_app
                )
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
                session_changed = (
                    state is not None
                    and state.session_key != candidate["host_session_key"]
                )
                if session_changed:
                    _close_episode(
                        repo_id=repo_id,
                        host_app=host_app,
                        host_session_key=state.session_key,
                        uow_factory=uow_factory,
                    )

                freshness = float(candidate.get("updated_at") or 0.0)
                should_sync = (
                    state is None
                    or session_changed
                    or state.last_freshness != freshness
                )
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
                    record_episode_sync_status(
                        repo_root=repo_root,
                        host_app=host_app,
                        host_session_key=str(candidate["host_session_key"]),
                        last_successful_sync_at=_utc_now().isoformat(),
                        last_error=None,
                    )
                    try:
                        model_usage_records = tuple(
                            collect_model_usage_records_for_session(
                                repo_id=repo_id,
                                host_app=host_app,
                                host_session_key=str(candidate["host_session_key"]),
                                thread_id=str(sync_result["thread_id"]),
                                episode_id=str(sync_result["episode_id"]),
                                transcript_path=Path(
                                    str(sync_result["transcript_path"])
                                ),
                            )
                        )
                    except Exception:
                        model_usage_records = ()
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
                        model_usage_records=model_usage_records,
                    )
                    saw_change = True
                except Exception as exc:
                    record_episode_sync_status(
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
                        model_usage_records=(),
                    )

            if saw_change:
                last_change_at = time.monotonic()
            elif time.monotonic() - last_change_at >= IDLE_EXIT_SECONDS:
                break

            time.sleep(POLL_INTERVAL_SECONDS)
    finally:
        lock_handle.release()


def _close_episode(
    *, repo_id: str, host_app: str, host_session_key: str, uow_factory
) -> None:
    """Close one active episode when a newer session replaces it."""

    with uow_factory() as uow:
        close_replaced_episode(
            repo_id=repo_id,
            host_app=host_app,
            host_session_key=host_session_key,
            ended_at=_utc_now(),
            uow=uow,
        )


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
        record_episode_sync_status(
            repo_root=repo_root,
            host_app=host_app,
            host_session_key=host_session_key,
            last_successful_sync_at=None,
            last_error=str(exc),
        )


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
    model_usage_records=(),
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
            created_at=_utc_now(),
        )
        with uow_factory() as uow:
            record_episode_sync_telemetry(uow=uow, run=run, tool_types=tool_types)
            if model_usage_records:
                record_model_usage_telemetry(
                    uow=uow,
                    records=tuple(model_usage_records),
                )
    except Exception:
        return
