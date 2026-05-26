"""Unit coverage for snapshot-backed code-delta context."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.entities.snapshots import (
    AvailableCodeDeltaContext,
    CodeDeltaUnavailableReason,
    ShadowGitDiffResult,
    ShadowGitPathChange,
    ShadowGitPathChangeStatus,
    ShadowSnapshot,
    ShadowSnapshotReason,
    UnavailableCodeDeltaContext,
)
from app.core.use_cases.snapshots.code_delta_context import (
    CodeDeltaContextRequest,
    build_code_delta_context_for_event_window,
    build_code_delta_context_from_snapshots,
)


def test_code_delta_context_is_available_for_valid_snapshot_pair() -> None:
    """A bounded event window should expose compact patch identity when snapshots fit."""

    uow = _FakeUnitOfWork(
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
    )

    result = build_code_delta_context_for_event_window(
        _request(),
        uow,
        shadow_git_store=_FakeShadowGitStore(),
    )

    assert isinstance(result, AvailableCodeDeltaContext)
    assert result.to_response_data() == {
        "status": "available",
        "base_snapshot_id": "snap-base",
        "final_snapshot_id": "snap-final",
        "base_shadow_commit_sha": "commit-base",
        "final_shadow_commit_sha": "commit-final",
        "patch_sha": "patch-sha",
        "path_changes": [{"status": "modified", "path": "app/example.py"}],
        "changed_paths": ["app/example.py"],
    }


def test_code_delta_context_reports_missing_base_snapshot() -> None:
    """Absent base evidence should be an explicit unavailable state."""

    result = build_code_delta_context_for_event_window(
        _request(),
        _FakeUnitOfWork(snapshots=[]),
        shadow_git_store=_FakeShadowGitStore(),
    )

    assert _unavailable_reason(result) is CodeDeltaUnavailableReason.MISSING_BASE_SNAPSHOT


def test_code_delta_context_reports_missing_final_snapshot() -> None:
    """A window without a closeout snapshot should not pretend to have code context."""

    result = build_code_delta_context_for_event_window(
        _request(),
        _FakeUnitOfWork(
            snapshots=[
                _snapshot(
                    snapshot_id="snap-base",
                    commit_sha="commit-base",
                    reason=ShadowSnapshotReason.BASELINE,
                    event_seq=3,
                )
            ]
        ),
        shadow_git_store=_FakeShadowGitStore(),
    )

    assert _unavailable_reason(result) is CodeDeltaUnavailableReason.MISSING_FINAL_SNAPSHOT


def test_code_delta_context_rejects_baseline_only_base_without_event_boundary() -> None:
    """A baseline-only base without sequence proof should not become trusted evidence."""

    result = build_code_delta_context_for_event_window(
        _request(),
        _FakeUnitOfWork(
            snapshots=[
                _snapshot(
                    snapshot_id="snap-base",
                    commit_sha="commit-base",
                    reason=ShadowSnapshotReason.BASELINE_ONLY,
                    event_seq=None,
                ),
                _snapshot(
                    snapshot_id="snap-final",
                    commit_sha="commit-final",
                    reason=ShadowSnapshotReason.CLOSEOUT,
                    event_seq=5,
                ),
            ]
        ),
        shadow_git_store=_FakeShadowGitStore(),
    )

    assert (
        _unavailable_reason(result)
        is CodeDeltaUnavailableReason.BASELINE_ONLY_BASE_SNAPSHOT
    )


def test_code_delta_context_rejects_matching_snapshot_pair() -> None:
    """A pair must identify two distinct repo states."""

    snapshot = _snapshot(
        snapshot_id="snap-same",
        commit_sha="commit-same",
        reason=ShadowSnapshotReason.CLOSEOUT,
        event_seq=5,
    )
    result = build_code_delta_context_from_snapshots(
        repo_root="/repo",
        base_snapshot=snapshot,
        final_snapshot=snapshot,
        baseline_only_base_event_seq=4,
        shadow_git_store=_FakeShadowGitStore(),
    )

    assert (
        _unavailable_reason(result)
        is CodeDeltaUnavailableReason.BASE_AND_FINAL_SNAPSHOT_MATCH
    )


def test_code_delta_context_rejects_baseline_only_final_snapshot() -> None:
    """A first closeout snapshot should not become a final delta endpoint."""

    result = build_code_delta_context_from_snapshots(
        repo_root="/repo",
        base_snapshot=_snapshot(
            snapshot_id="snap-base",
            commit_sha="commit-base",
            reason=ShadowSnapshotReason.BASELINE,
            event_seq=3,
        ),
        final_snapshot=_snapshot(
            snapshot_id="snap-final",
            commit_sha="commit-final",
            reason=ShadowSnapshotReason.BASELINE_ONLY,
            event_seq=5,
        ),
        baseline_only_base_event_seq=3,
        shadow_git_store=_FakeShadowGitStore(),
    )

    assert (
        _unavailable_reason(result)
        is CodeDeltaUnavailableReason.BASELINE_ONLY_FINAL_SNAPSHOT
    )


def test_code_delta_context_rejects_empty_git_delta() -> None:
    """Distinct snapshots with no path changes should stay unavailable."""

    result = build_code_delta_context_for_event_window(
        _request(),
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
        shadow_git_store=_FakeShadowGitStore(path_changes=()),
    )

    assert _unavailable_reason(result) is CodeDeltaUnavailableReason.EMPTY_DELTA


def _request() -> CodeDeltaContextRequest:
    return CodeDeltaContextRequest(
        repo_id="repo-a",
        repo_root="/repo",
        episode_id="episode-1",
        after_seq=3,
        up_to_seq=5,
    )


def _unavailable_reason(result) -> CodeDeltaUnavailableReason:
    assert isinstance(result, UnavailableCodeDeltaContext)
    return result.reason


class _FakeUnitOfWork:
    def __init__(self, *, snapshots: list[ShadowSnapshot]) -> None:
        self.snapshots = _FakeSnapshotsRepo(snapshots=snapshots)


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
    def __init__(
        self, *, path_changes: tuple[ShadowGitPathChange, ...] | None = None
    ) -> None:
        if path_changes is None:
            path_changes = (
                ShadowGitPathChange(
                    status=ShadowGitPathChangeStatus.MODIFIED,
                    path="app/example.py",
                ),
            )
        self._path_changes = path_changes

    def diff_snapshot_pair(self, **kwargs) -> ShadowGitDiffResult:
        assert kwargs["base_commit_sha"] == "commit-base"
        assert kwargs["final_commit_sha"] == "commit-final"
        return ShadowGitDiffResult(
            patch_sha="patch-sha",
            path_changes=self._path_changes,
        )

    def capture_snapshot(self, request):  # pragma: no cover - context tests do not capture
        raise AssertionError("code delta context should not capture snapshots")


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
