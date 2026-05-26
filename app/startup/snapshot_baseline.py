"""Startup-owned wiring for automatic shadow snapshot baselines."""

from __future__ import annotations

from app.core.entities.snapshots import ShadowSnapshotReason
from app.core.use_cases.snapshots.capture_snapshot import (
    CaptureSnapshotRequest,
    execute_ensure_baseline_snapshot,
)
from app.infrastructure.local_state.repo_registration_store import resolve_git_root
from app.infrastructure.local_state.shadow_git_store import ShadowGitStore
from app.infrastructure.system.clock import SystemClock
from app.infrastructure.system.id_generator import UuidGenerator
from app.startup import use_cases


def ensure_shadow_baseline_for_operation(
    *, repo_context, operation_invocation_id: str
) -> None:
    """Create a valid repo baseline before later solution snapshots rely on it."""

    repo_root = repo_context.registration_root
    if repo_root is None:
        return
    git_root = resolve_git_root(repo_root)
    if git_root is None:
        return
    with use_cases.get_uow_factory()() as uow:
        execute_ensure_baseline_snapshot(
            CaptureSnapshotRequest(
                repo_id=repo_context.repo_id,
                repo_root=str(git_root),
                reason=ShadowSnapshotReason.BASELINE,
                operation_invocation_id=operation_invocation_id,
            ),
            uow,
            shadow_git_store=ShadowGitStore(),
            id_generator=UuidGenerator(),
            clock=SystemClock(),
        )
