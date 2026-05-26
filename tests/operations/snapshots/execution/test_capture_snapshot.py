"""Unit coverage for shadow snapshot capture orchestration."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.entities.snapshots import (
    ShadowGitCaptureResult,
    ShadowGitCaptureState,
    ShadowSnapshot,
    ShadowSnapshotReason,
    SnapshotCaptureStatus,
)
from app.core.use_cases.snapshots.capture_snapshot import (
    CaptureSnapshotRequest,
    execute_capture_snapshot,
    execute_ensure_baseline_snapshot,
)


def test_first_closeout_snapshot_is_baseline_only() -> None:
    """A first closeout capture should not pretend to prove a prior code delta."""

    uow = _FakeUnitOfWork()

    result = execute_capture_snapshot(
        CaptureSnapshotRequest(
            repo_id="repo-a",
            repo_root="/repo",
            reason=ShadowSnapshotReason.CLOSEOUT,
            episode_id="episode-1",
            captured_after_event_seq=12,
            operation_invocation_id="op-1",
        ),
        uow,
        shadow_git_store=_FakeShadowGitStore(state=ShadowGitCaptureState.CREATED),
        id_generator=_IdGen(),
        clock=_Clock(),
    )

    assert result.status is SnapshotCaptureStatus.BASELINE_ONLY
    assert result.reason == "baseline_only"
    assert len(uow.snapshots.rows) == 1
    assert uow.snapshots.rows[0].reason is ShadowSnapshotReason.BASELINE_ONLY


def test_baseline_capture_is_valid_baseline_when_no_snapshot_exists() -> None:
    """Automatic baselines should be stored as valid baseline evidence."""

    uow = _FakeUnitOfWork()

    result = execute_ensure_baseline_snapshot(
        CaptureSnapshotRequest(
            repo_id="repo-a",
            repo_root="/repo",
            reason=ShadowSnapshotReason.BASELINE,
            operation_invocation_id="op-1",
        ),
        uow,
        shadow_git_store=_FakeShadowGitStore(state=ShadowGitCaptureState.CREATED),
        id_generator=_IdGen(),
        clock=_Clock(),
    )

    assert result.status is SnapshotCaptureStatus.CREATED
    assert result.reason == "baseline"
    assert uow.snapshots.rows[0].reason is ShadowSnapshotReason.BASELINE


def test_noop_capture_does_not_persist_duplicate_snapshot() -> None:
    """Matching trees should return noop without adding a metadata row."""

    existing = ShadowSnapshot(
        id="snap-existing",
        repo_id="repo-a",
        repo_root="/repo",
        shadow_commit_sha="commit-existing",
        changed_paths=(),
        reason=ShadowSnapshotReason.BASELINE,
    )
    uow = _FakeUnitOfWork(rows=[existing])

    result = execute_capture_snapshot(
        CaptureSnapshotRequest(
            repo_id="repo-a",
            repo_root="/repo",
            reason=ShadowSnapshotReason.CLOSEOUT,
        ),
        uow,
        shadow_git_store=_FakeShadowGitStore(state=ShadowGitCaptureState.NOOP),
        id_generator=_IdGen(),
        clock=_Clock(),
    )

    assert result.status is SnapshotCaptureStatus.NOOP
    assert result.shadow_commit_sha == "commit-existing"
    assert uow.snapshots.rows == [existing]


class _Clock:
    def now(self):
        return datetime(2026, 5, 26, 12, tzinfo=timezone.utc)


class _IdGen:
    def new_id(self) -> str:
        return "snap-1"


class _FakeUnitOfWork:
    def __init__(self, *, rows: list[ShadowSnapshot] | None = None) -> None:
        self.snapshots = _FakeSnapshotsRepo(rows=rows or [])


class _FakeSnapshotsRepo:
    def __init__(self, *, rows: list[ShadowSnapshot]) -> None:
        self.rows = rows

    def latest_snapshot(self, **kwargs) -> ShadowSnapshot | None:
        del kwargs
        return self.rows[-1] if self.rows else None

    def add_snapshot(self, snapshot: ShadowSnapshot) -> None:
        self.rows.append(snapshot)


class _FakeShadowGitStore:
    def __init__(self, *, state: ShadowGitCaptureState) -> None:
        self._state = state

    def capture_snapshot(self, request):
        if self._state is ShadowGitCaptureState.NOOP:
            return ShadowGitCaptureResult(
                state=ShadowGitCaptureState.NOOP,
                shadow_commit_sha="commit-existing",
                parent_shadow_commit_sha="commit-existing",
                changed_paths=(),
            )
        return ShadowGitCaptureResult(
            state=ShadowGitCaptureState.CREATED,
            shadow_commit_sha="commit-new",
            parent_shadow_commit_sha=None,
            changed_paths=("app/example.py",),
        )

    def diff_snapshot_pair(self, **kwargs):  # pragma: no cover - capture tests do not diff
        raise AssertionError("capture tests should not diff snapshots")
