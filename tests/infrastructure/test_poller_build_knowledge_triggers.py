"""Poller trigger coverage for build_knowledge stable-watermark runs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.entities.episodes import EpisodeBuildSnapshot, EpisodeStatus
from app.core.entities.knowledge_builder import KnowledgeBuildTrigger
from app.infrastructure.process.episode_sync.poller import run_episode_poller


OLD = datetime(2000, 1, 1, tzinfo=timezone.utc)
FUTURE = datetime(3026, 5, 19, 11, tzinfo=timezone.utc)


def test_poller_syncs_multiple_sessions_for_one_host(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """poller should sync every repo-matching session, not only the latest."""

    sync_calls: list[dict[str, object]] = []
    _patch_common_poller_edges(monkeypatch)
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.discover_host_sessions",
        lambda **kwargs: (
            [
                _candidate(tmp_path, "thread-a", 1.0),
                _candidate(tmp_path, "thread-b", 2.0),
            ]
            if kwargs["host_app"] == "codex"
            else []
        ),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.sync_episode_from_host",
        lambda **kwargs: (
            sync_calls.append(kwargs)
            or _sync_result(
                episode_id=f"ep-{kwargs['host_session_key']}",
                thread_id=f"codex:{kwargs['host_session_key']}",
                tmp_path=tmp_path,
            )
        ),
    )

    run_episode_poller(
        repo_id="repo-a",
        repo_root=tmp_path,
        uow_factory=lambda: _FakeUnitOfWork(snapshots=()),
        idle_stable_seconds=0,
    )

    assert [call["host_session_key"] for call in sync_calls] == [
        "thread-a",
        "thread-b",
    ]


def test_focus_switch_does_not_emit_replacement_build(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """seeing a different latest session should not close or build the old one."""

    build_calls: list[dict[str, object]] = []
    discoveries = {"count": 0}
    _patch_common_poller_edges(monkeypatch)

    def _discover(**kwargs):
        if kwargs["host_app"] != "codex":
            return []
        discoveries["count"] += 1
        session_key = "thread-old" if discoveries["count"] == 1 else "thread-new"
        updated_at = 1.0 if session_key == "thread-old" else 2.0
        return [_candidate(tmp_path, session_key, updated_at)]

    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.discover_host_sessions",
        _discover,
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.sync_episode_from_host",
        lambda **kwargs: _sync_result(
            episode_id=f"ep-{kwargs['host_session_key']}",
            thread_id=f"codex:{kwargs['host_session_key']}",
            tmp_path=tmp_path,
        ),
    )

    run_episode_poller(
        repo_id="repo-a",
        repo_root=tmp_path,
        uow_factory=lambda: _FakeUnitOfWork(snapshots=()),
        run_build_knowledge=lambda **kwargs: build_calls.append(kwargs),
        idle_stable_seconds=0,
    )

    assert all(
        call["trigger"] is not KnowledgeBuildTrigger.SESSION_REPLACED
        for call in build_calls
    )


def test_poller_runs_build_for_stable_active_episode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """active episodes build once their persisted event watermark is stable."""

    calls: list[dict[str, object]] = []
    snapshots = {
        "ep-1": _snapshot(
            episode_id="ep-1",
            status=EpisodeStatus.ACTIVE,
            latest_event_seq=8,
            latest_event_at=OLD,
            latest_successful_build_watermark=3,
        )
    }
    _patch_no_discovery(monkeypatch)

    run_episode_poller(
        repo_id="repo-a",
        repo_root=tmp_path,
        uow_factory=lambda: _FakeUnitOfWork(snapshots=snapshots.values()),
        run_build_knowledge=_record_build_and_mark(calls, snapshots),
        idle_stable_seconds=0,
    )

    assert calls == [
        {
            "repo_id": "repo-a",
            "repo_root": tmp_path.resolve(),
            "episode_id": "ep-1",
            "trigger": KnowledgeBuildTrigger.WATERMARK_STABLE,
        }
    ]


def test_poller_does_not_build_recent_active_episode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """active episodes with recent events are not stable enough to build."""

    calls: list[dict[str, object]] = []
    _patch_no_discovery(monkeypatch)

    run_episode_poller(
        repo_id="repo-a",
        repo_root=tmp_path,
        uow_factory=lambda: _FakeUnitOfWork(
            snapshots=(
                _snapshot(
                    episode_id="ep-1",
                    status=EpisodeStatus.ACTIVE,
                    latest_event_seq=8,
                    latest_event_at=FUTURE,
                    latest_successful_build_watermark=3,
                ),
            )
        ),
        run_build_knowledge=lambda **kwargs: calls.append(kwargs),
        idle_stable_seconds=0,
    )

    assert calls == []


def test_poller_builds_closed_episode_immediately(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """closed episodes do not need idle age once they have unbuilt events."""

    calls: list[dict[str, object]] = []
    snapshots = {
        "ep-1": _snapshot(
            episode_id="ep-1",
            status=EpisodeStatus.CLOSED,
            latest_event_seq=8,
            latest_event_at=FUTURE,
            latest_successful_build_watermark=3,
        )
    }
    _patch_no_discovery(monkeypatch)

    run_episode_poller(
        repo_id="repo-a",
        repo_root=tmp_path,
        uow_factory=lambda: _FakeUnitOfWork(snapshots=snapshots.values()),
        run_build_knowledge=_record_build_and_mark(calls, snapshots),
        idle_stable_seconds=0,
    )

    assert calls == [
        {
            "repo_id": "repo-a",
            "repo_root": tmp_path.resolve(),
            "episode_id": "ep-1",
            "trigger": KnowledgeBuildTrigger.WATERMARK_STABLE,
        }
    ]


def test_poller_skips_episode_with_current_successful_watermark(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """episodes already built through the latest event seq should not run again."""

    calls: list[dict[str, object]] = []
    _patch_no_discovery(monkeypatch)

    run_episode_poller(
        repo_id="repo-a",
        repo_root=tmp_path,
        uow_factory=lambda: _FakeUnitOfWork(
            snapshots=(
                _snapshot(
                    episode_id="ep-1",
                    status=EpisodeStatus.ACTIVE,
                    latest_event_seq=8,
                    latest_event_at=OLD,
                    latest_successful_build_watermark=8,
                ),
            )
        ),
        run_build_knowledge=lambda **kwargs: calls.append(kwargs),
        idle_stable_seconds=0,
    )

    assert calls == []


def test_poller_builds_stable_episode_after_restart(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """stable builds should rely on persisted snapshots, not in-memory state."""

    calls: list[dict[str, object]] = []
    snapshots = {
        "ep-1": _snapshot(
            episode_id="ep-1",
            status=EpisodeStatus.ACTIVE,
            latest_event_seq=8,
            latest_event_at=OLD,
            latest_successful_build_watermark=None,
        )
    }
    _patch_no_discovery(monkeypatch)

    run_episode_poller(
        repo_id="repo-a",
        repo_root=tmp_path,
        uow_factory=lambda: _FakeUnitOfWork(snapshots=snapshots.values()),
        run_build_knowledge=_record_build_and_mark(calls, snapshots),
        idle_stable_seconds=0,
    )

    assert calls[0]["episode_id"] == "ep-1"
    assert calls[0]["trigger"] is KnowledgeBuildTrigger.WATERMARK_STABLE


def test_recent_active_episode_does_not_block_stable_episode_build(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """one noisy active session should not block another stable episode."""

    calls: list[dict[str, object]] = []
    snapshots = {
        "ep-stable": _snapshot(
            episode_id="ep-stable",
            status=EpisodeStatus.ACTIVE,
            latest_event_seq=8,
            latest_event_at=OLD,
            latest_successful_build_watermark=3,
        ),
        "ep-noisy": _snapshot(
            episode_id="ep-noisy",
            status=EpisodeStatus.ACTIVE,
            latest_event_seq=5,
            latest_event_at=FUTURE,
            latest_successful_build_watermark=1,
        ),
    }
    _patch_no_discovery(monkeypatch)

    run_episode_poller(
        repo_id="repo-a",
        repo_root=tmp_path,
        uow_factory=lambda: _FakeUnitOfWork(snapshots=snapshots.values()),
        run_build_knowledge=_record_build_and_mark(calls, snapshots),
        idle_stable_seconds=0,
    )

    assert [call["episode_id"] for call in calls] == ["ep-stable"]


def _patch_common_poller_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch process and telemetry edges away from poller trigger tests."""

    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.SUPPORTED_HOSTS",
        ("codex",),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.acquire_poller_lock",
        lambda **kwargs: _NoOpLock(),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.write_poller_pid_artifact",
        lambda **kwargs: Path("/tmp/episode_sync.pid"),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.POLL_INTERVAL_SECONDS",
        0,
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.default_search_roots",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.collect_model_usage_records_for_session",
        lambda **kwargs: (),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller._record_sync_telemetry_best_effort",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.record_episode_sync_status",
        lambda **kwargs: None,
    )


def _patch_no_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the poller to exercise persisted build snapshots only."""

    _patch_common_poller_edges(monkeypatch)
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.discover_host_sessions",
        lambda **kwargs: [],
    )


def _candidate(tmp_path: Path, session_key: str, updated_at: float) -> dict[str, object]:
    """Return one transcript discovery candidate."""

    return {
        "host_app": "codex",
        "host_session_key": session_key,
        "transcript_path": tmp_path / f"{session_key}.jsonl",
        "updated_at": updated_at,
    }


def _sync_result(episode_id: str, thread_id: str, tmp_path: Path) -> dict[str, object]:
    """Return a poller sync result payload."""

    return {
        "thread_id": thread_id,
        "episode_id": episode_id,
        "transcript_path": str(tmp_path / "transcript.jsonl"),
        "imported_event_count": 1,
        "total_event_count": 1,
        "user_event_count": 1,
        "assistant_event_count": 0,
        "tool_event_count": 0,
        "system_event_count": 0,
        "tool_type_counts": {},
    }


def _snapshot(
    *,
    episode_id: str,
    status: EpisodeStatus,
    latest_event_seq: int,
    latest_event_at: datetime,
    latest_successful_build_watermark: int | None,
) -> EpisodeBuildSnapshot:
    """Return one build-planning snapshot."""

    return EpisodeBuildSnapshot(
        episode_id=episode_id,
        status=status,
        latest_event_seq=latest_event_seq,
        latest_event_at=latest_event_at,
        latest_successful_build_watermark=latest_successful_build_watermark,
    )


def _record_build_and_mark(
    calls: list[dict[str, object]],
    snapshots: dict[str, EpisodeBuildSnapshot],
):
    """Return a fake builder that marks each built snapshot current."""

    def _run(**kwargs) -> None:
        calls.append(kwargs)
        snapshot = snapshots[str(kwargs["episode_id"])]
        snapshots[snapshot.episode_id] = _snapshot(
            episode_id=snapshot.episode_id,
            status=snapshot.status,
            latest_event_seq=snapshot.latest_event_seq,
            latest_event_at=snapshot.latest_event_at,
            latest_successful_build_watermark=snapshot.latest_event_seq,
        )

    return _run


class _FakeEpisodesRepo:
    """Minimal episode repo for stable build planning tests."""

    def __init__(self, *, snapshots) -> None:
        self._snapshots = snapshots

    def list_build_snapshots(self, *, repo_id: str):
        del repo_id
        return tuple(self._snapshots)


class _FakeUnitOfWork:
    """Minimal context-manager unit of work."""

    def __init__(self, *, snapshots) -> None:
        self.episodes = _FakeEpisodesRepo(snapshots=snapshots)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


class _NoOpLock:
    """Minimal poller lock test double."""

    def release(self) -> None:
        return None
