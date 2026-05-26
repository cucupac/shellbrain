"""Core orchestration for snapshot-backed code-delta context."""

from __future__ import annotations

from app.core.entities.snapshots import (
    AvailableCodeDeltaContext,
    CodeDeltaContext,
    CodeDeltaUnavailableReason,
    ShadowSnapshot,
    ShadowSnapshotReason,
    UnavailableCodeDeltaContext,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.local_state.shadow_git import IShadowGitStore
from app.core.use_cases.snapshots.code_delta_context.request import (
    CodeDeltaContextRequest,
)


def build_code_delta_context_for_event_window(
    request: CodeDeltaContextRequest,
    uow: IUnitOfWork,
    *,
    shadow_git_store: IShadowGitStore,
) -> CodeDeltaContext:
    """Return compact code-delta context for a bounded event window."""

    base_snapshot = uow.snapshots.latest_snapshot_at_or_before_event(
        repo_id=request.repo_id,
        repo_root=request.repo_root,
        episode_id=request.episode_id,
        event_seq=request.after_seq,
    )
    if base_snapshot is None:
        return _unavailable(CodeDeltaUnavailableReason.MISSING_BASE_SNAPSHOT)

    final_snapshot = uow.snapshots.latest_snapshot_in_event_window(
        repo_id=request.repo_id,
        repo_root=request.repo_root,
        episode_id=request.episode_id,
        opened_event_seq=request.after_seq + 1,
        closed_event_seq=request.up_to_seq,
    )
    if final_snapshot is None:
        return _unavailable(CodeDeltaUnavailableReason.MISSING_FINAL_SNAPSHOT)

    return build_code_delta_context_from_snapshots(
        repo_root=request.repo_root,
        base_snapshot=base_snapshot,
        final_snapshot=final_snapshot,
        baseline_only_base_event_seq=request.after_seq,
        shadow_git_store=shadow_git_store,
    )


def build_code_delta_context_from_snapshots(
    *,
    repo_root: str,
    base_snapshot: ShadowSnapshot,
    final_snapshot: ShadowSnapshot,
    baseline_only_base_event_seq: int,
    shadow_git_store: IShadowGitStore,
) -> CodeDeltaContext:
    """Return compact code-delta context for an already-selected snapshot pair."""

    if base_snapshot.id == final_snapshot.id:
        return _unavailable(CodeDeltaUnavailableReason.BASE_AND_FINAL_SNAPSHOT_MATCH)
    if final_snapshot.reason is ShadowSnapshotReason.BASELINE_ONLY:
        return _unavailable(CodeDeltaUnavailableReason.BASELINE_ONLY_FINAL_SNAPSHOT)
    if not _baseline_only_base_predates_window(
        base_snapshot=base_snapshot,
        event_seq=baseline_only_base_event_seq,
    ):
        return _unavailable(CodeDeltaUnavailableReason.BASELINE_ONLY_BASE_SNAPSHOT)

    patch = shadow_git_store.diff_snapshot_pair(
        repo_root=repo_root,
        base_commit_sha=base_snapshot.shadow_commit_sha,
        final_commit_sha=final_snapshot.shadow_commit_sha,
    )
    if not patch.path_changes:
        return _unavailable(CodeDeltaUnavailableReason.EMPTY_DELTA)
    return AvailableCodeDeltaContext(
        base_snapshot_id=base_snapshot.id,
        final_snapshot_id=final_snapshot.id,
        base_shadow_commit_sha=base_snapshot.shadow_commit_sha,
        final_shadow_commit_sha=final_snapshot.shadow_commit_sha,
        patch_sha=patch.patch_sha,
        path_changes=patch.path_changes,
    )


def _baseline_only_base_predates_window(
    *, base_snapshot: ShadowSnapshot, event_seq: int
) -> bool:
    """Return whether a baseline-only snapshot can serve as this window's base."""

    if base_snapshot.reason is not ShadowSnapshotReason.BASELINE_ONLY:
        return True
    return (
        base_snapshot.captured_after_event_seq is not None
        and base_snapshot.captured_after_event_seq <= event_seq
    )


def _unavailable(reason: CodeDeltaUnavailableReason) -> UnavailableCodeDeltaContext:
    return UnavailableCodeDeltaContext(reason=reason)
