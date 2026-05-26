"""Handler coverage for code-delta context on bounded events reads."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from app.core.entities.episodes import Episode, EpisodeEvent, EpisodeEventSource
from app.core.entities.runtime_context import RuntimeContext
from app.core.entities.snapshots import (
    ShadowGitDiffResult,
    ShadowGitPathChange,
    ShadowGitPathChangeStatus,
    ShadowSnapshot,
    ShadowSnapshotReason,
)
from app.core.use_cases.episodes.events.request import EpisodeEventsRequest
from app.entrypoints.cli.handlers.internal_agent.episodes.events import (
    run_read_events_operation,
)
from app.startup.operation_dependencies import build_operation_dependencies


def test_bounded_events_response_includes_code_delta_context() -> None:
    """The builder's bounded events read should include compact code-delta evidence."""

    result = _run_events(
        EpisodeEventsRequest(
            repo_id="repo-a",
            episode_id="episode-1",
            after_seq=3,
            up_to_seq=5,
        ),
        _FakeUnitOfWork(
            snapshots=[
                _snapshot(
                    snapshot_id="snap-base",
                    commit_sha="commit-base",
                    reason=ShadowSnapshotReason.BASELINE,
                    event_seq=3,
                ),
                _snapshot(
                    snapshot_id="snap-final",
                    commit_sha="commit-final",
                    reason=ShadowSnapshotReason.CLOSEOUT,
                    event_seq=5,
                ),
            ]
        ),
    )

    assert result["status"] == "ok"
    assert result["data"]["event_range"] == {
        "after_seq": 3,
        "up_to_seq": 5,
        "order": "oldest_first",
        "returned_count": 2,
        "expected_count": 2,
        "complete": True,
    }
    assert result["data"]["code_delta_context"] == {
        "status": "available",
        "base_snapshot_id": "snap-base",
        "final_snapshot_id": "snap-final",
        "base_shadow_commit_sha": "commit-base",
        "final_shadow_commit_sha": "commit-final",
        "patch_sha": "patch-sha",
        "path_changes": [{"status": "modified", "path": "app/example.py"}],
        "changed_paths": ["app/example.py"],
    }


def test_unbounded_events_response_omits_code_delta_context() -> None:
    """Recent-events reads should not grow a delta context outside a bounded range."""

    result = _run_events(
        EpisodeEventsRequest(repo_id="repo-a", episode_id="episode-1", limit=2),
        _FakeUnitOfWork(snapshots=[]),
        shadow_git_store=_NoDiffShadowGitStore(),
    )

    assert result["status"] == "ok"
    assert "event_range" not in result["data"]
    assert "code_delta_context" not in result["data"]


def _run_events(
    request: EpisodeEventsRequest,
    uow,
    *,
    shadow_git_store=None,
) -> dict:
    dependencies = replace(
        build_operation_dependencies(),
        shadow_git_store=shadow_git_store or _FakeShadowGitStore(),
        telemetry_sink=_FakeTelemetrySink(),
    )
    return run_read_events_operation(
        request,
        dependencies=dependencies,
        uow_factory=lambda: uow,
        inferred_repo_id="repo-a",
        repo_root=Path("/repo"),
        telemetry_context=RuntimeContext(invocation_id="op-1", repo_root="/repo"),
    )


class _FakeTelemetrySink:
    def record(self, **kwargs) -> None:
        del kwargs


class _FakeUnitOfWork:
    def __init__(self, *, snapshots: list[ShadowSnapshot]) -> None:
        self.episodes = _FakeEpisodesRepo()
        self.snapshots = _FakeSnapshotsRepo(snapshots=snapshots)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        del exc_type, exc_val, exc_tb


class _FakeEpisodesRepo:
    def __init__(self) -> None:
        self._episode = Episode(
            id="episode-1",
            repo_id="repo-a",
            host_app="codex",
            thread_id="thread-1",
        )
        self._events = [
            EpisodeEvent(
                id=f"evt-{seq}",
                episode_id="episode-1",
                seq=seq,
                host_event_key=f"event-{seq}",
                source=EpisodeEventSource.USER,
                content=f"event {seq}",
                created_at=datetime(2026, 5, 26, 12, seq, tzinfo=timezone.utc),
            )
            for seq in range(1, 6)
        ]

    def get_episode(self, *, repo_id: str, episode_id: str) -> Episode | None:
        if repo_id != "repo-a" or episode_id != "episode-1":
            return None
        return self._episode

    def list_events_range(
        self, *, repo_id: str, episode_id: str, after_seq: int, up_to_seq: int
    ) -> list[EpisodeEvent]:
        del repo_id, episode_id
        return [
            event for event in self._events if after_seq < event.seq <= up_to_seq
        ]

    def list_recent_events(
        self, *, repo_id: str, episode_id: str, limit: int
    ) -> list[EpisodeEvent]:
        del repo_id, episode_id
        return list(reversed(self._events[-limit:]))


class _FakeSnapshotsRepo:
    def __init__(self, *, snapshots: list[ShadowSnapshot]) -> None:
        self._snapshots = snapshots

    def latest_snapshot_at_or_before_event(
        self, *, event_seq: int, **kwargs
    ) -> ShadowSnapshot | None:
        del kwargs
        candidates = [
            snapshot
            for snapshot in self._snapshots
            if snapshot.captured_after_event_seq is None
            or snapshot.captured_after_event_seq <= event_seq
        ]
        return candidates[-1] if candidates else None

    def latest_snapshot_in_event_window(
        self, *, opened_event_seq: int, closed_event_seq: int, **kwargs
    ) -> ShadowSnapshot | None:
        del kwargs
        candidates = [
            snapshot
            for snapshot in self._snapshots
            if snapshot.reason is not ShadowSnapshotReason.BASELINE_ONLY
            and snapshot.captured_after_event_seq is not None
            and opened_event_seq <= snapshot.captured_after_event_seq <= closed_event_seq
        ]
        return candidates[-1] if candidates else None


class _FakeShadowGitStore:
    def diff_snapshot_pair(self, **kwargs) -> ShadowGitDiffResult:
        assert kwargs["base_commit_sha"] == "commit-base"
        assert kwargs["final_commit_sha"] == "commit-final"
        return ShadowGitDiffResult(
            patch_sha="patch-sha",
            path_changes=(
                ShadowGitPathChange(
                    status=ShadowGitPathChangeStatus.MODIFIED,
                    path="app/example.py",
                ),
            ),
        )

    def capture_snapshot(self, request):  # pragma: no cover - events should not capture
        raise AssertionError("events should not capture snapshots")


class _NoDiffShadowGitStore(_FakeShadowGitStore):
    def diff_snapshot_pair(self, **kwargs) -> ShadowGitDiffResult:
        raise AssertionError("unbounded events should not diff snapshots")


def _snapshot(
    *,
    snapshot_id: str,
    commit_sha: str,
    reason: ShadowSnapshotReason,
    event_seq: int | None,
) -> ShadowSnapshot:
    return ShadowSnapshot(
        id=snapshot_id,
        repo_id="repo-a",
        repo_root="/repo",
        episode_id="episode-1",
        captured_after_event_seq=event_seq,
        shadow_commit_sha=commit_sha,
        parent_shadow_commit_sha=None,
        changed_paths=(),
        reason=reason,
        created_at=datetime(2026, 5, 26, 12, tzinfo=timezone.utc),
    )
