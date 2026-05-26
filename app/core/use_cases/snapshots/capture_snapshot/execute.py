"""Core orchestration for capturing repo-local shadow snapshots."""

from __future__ import annotations

from app.core.entities.snapshots import (
    ShadowGitCaptureRequest,
    ShadowGitCaptureState,
    ShadowSnapshot,
    ShadowSnapshotReason,
    SnapshotCaptureStatus,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.local_state.shadow_git import IShadowGitStore
from app.core.ports.system.clock import IClock
from app.core.ports.system.idgen import IIdGenerator
from app.core.use_cases.snapshots.capture_snapshot.request import (
    CaptureSnapshotRequest,
)
from app.core.use_cases.snapshots.capture_snapshot.result import CaptureSnapshotResult


def execute_capture_snapshot(
    request: CaptureSnapshotRequest,
    uow: IUnitOfWork,
    *,
    shadow_git_store: IShadowGitStore,
    id_generator: IIdGenerator,
    clock: IClock,
) -> CaptureSnapshotResult:
    """Capture repo state and persist metadata for a new shadow commit."""

    existing = uow.snapshots.latest_snapshot(
        repo_id=request.repo_id, repo_root=request.repo_root
    )
    reason = _effective_reason(request.reason, has_prior_snapshot=existing is not None)
    snapshot_id = id_generator.new_id()
    capture_result = shadow_git_store.capture_snapshot(
        ShadowGitCaptureRequest(
            snapshot_id=snapshot_id,
            repo_id=request.repo_id,
            repo_root=request.repo_root,
            reason=reason,
            episode_id=request.episode_id,
            captured_after_event_seq=request.captured_after_event_seq,
            operation_invocation_id=request.operation_invocation_id,
        )
    )
    if capture_result.state is ShadowGitCaptureState.NOOP:
        return CaptureSnapshotResult(
            status=SnapshotCaptureStatus.NOOP,
            snapshot_id=None,
            repo_id=request.repo_id,
            repo_root=request.repo_root,
            episode_id=request.episode_id,
            captured_after_event_seq=request.captured_after_event_seq,
            operation_invocation_id=request.operation_invocation_id,
            shadow_commit_sha=capture_result.shadow_commit_sha,
            parent_shadow_commit_sha=capture_result.parent_shadow_commit_sha,
            changed_paths=(),
            reason=reason.value,
        )

    assert capture_result.shadow_commit_sha is not None
    snapshot = ShadowSnapshot(
        id=snapshot_id,
        repo_id=request.repo_id,
        repo_root=request.repo_root,
        episode_id=request.episode_id,
        captured_after_event_seq=request.captured_after_event_seq,
        operation_invocation_id=request.operation_invocation_id,
        shadow_commit_sha=capture_result.shadow_commit_sha,
        parent_shadow_commit_sha=capture_result.parent_shadow_commit_sha,
        changed_paths=capture_result.changed_paths,
        reason=reason,
        created_at=clock.now(),
    )
    uow.snapshots.add_snapshot(snapshot)
    return CaptureSnapshotResult(
        status=_public_status_for_reason(reason),
        snapshot_id=snapshot.id,
        repo_id=snapshot.repo_id,
        repo_root=snapshot.repo_root,
        episode_id=snapshot.episode_id,
        captured_after_event_seq=snapshot.captured_after_event_seq,
        operation_invocation_id=snapshot.operation_invocation_id,
        shadow_commit_sha=snapshot.shadow_commit_sha,
        parent_shadow_commit_sha=snapshot.parent_shadow_commit_sha,
        changed_paths=snapshot.changed_paths,
        reason=snapshot.reason.value,
    )


def execute_ensure_baseline_snapshot(
    request: CaptureSnapshotRequest,
    uow: IUnitOfWork,
    *,
    shadow_git_store: IShadowGitStore,
    id_generator: IIdGenerator,
    clock: IClock,
) -> CaptureSnapshotResult:
    """Create a valid baseline snapshot only when a repo has none."""

    existing = uow.snapshots.latest_snapshot(
        repo_id=request.repo_id, repo_root=request.repo_root
    )
    if existing is not None:
        return CaptureSnapshotResult(
            status=SnapshotCaptureStatus.NOOP,
            snapshot_id=None,
            repo_id=request.repo_id,
            repo_root=request.repo_root,
            episode_id=request.episode_id,
            captured_after_event_seq=request.captured_after_event_seq,
            operation_invocation_id=request.operation_invocation_id,
            shadow_commit_sha=existing.shadow_commit_sha,
            parent_shadow_commit_sha=existing.parent_shadow_commit_sha,
            changed_paths=(),
            reason=existing.reason.value,
        )
    baseline_request = CaptureSnapshotRequest(
        repo_id=request.repo_id,
        repo_root=request.repo_root,
        reason=ShadowSnapshotReason.BASELINE,
        episode_id=request.episode_id,
        captured_after_event_seq=request.captured_after_event_seq,
        operation_invocation_id=request.operation_invocation_id,
    )
    return execute_capture_snapshot(
        baseline_request,
        uow,
        shadow_git_store=shadow_git_store,
        id_generator=id_generator,
        clock=clock,
    )


def _effective_reason(
    requested: ShadowSnapshotReason, *, has_prior_snapshot: bool
) -> ShadowSnapshotReason:
    """Return the persisted reason without pretending a first closeout is a delta."""

    if requested is ShadowSnapshotReason.CLOSEOUT and not has_prior_snapshot:
        return ShadowSnapshotReason.BASELINE_ONLY
    return requested


def _public_status_for_reason(reason: ShadowSnapshotReason) -> SnapshotCaptureStatus:
    """Map persisted snapshot reason to the command result state."""

    if reason is ShadowSnapshotReason.BASELINE_ONLY:
        return SnapshotCaptureStatus.BASELINE_ONLY
    return SnapshotCaptureStatus.CREATED
