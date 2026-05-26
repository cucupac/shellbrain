"""Result types for shadow snapshot capture."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.entities.snapshots import SnapshotCaptureStatus


@dataclass(frozen=True, kw_only=True)
class CaptureSnapshotResult:
    """Typed result for one shadow snapshot capture."""

    status: SnapshotCaptureStatus
    repo_id: str
    repo_root: str
    shadow_commit_sha: str | None
    parent_shadow_commit_sha: str | None
    changed_paths: tuple[str, ...]
    snapshot_id: str | None = None
    episode_id: str | None = None
    captured_after_event_seq: int | None = None
    operation_invocation_id: str | None = None
    reason: str | None = None

    @property
    def data(self) -> dict[str, object]:
        return self.to_response_data()

    def to_response_data(self) -> dict[str, object]:
        """Return the stable CLI response payload."""

        return {
            "result": self.status.value,
            "snapshot_id": self.snapshot_id,
            "repo_id": self.repo_id,
            "repo_root": self.repo_root,
            "episode_id": self.episode_id,
            "captured_after_event_seq": self.captured_after_event_seq,
            "operation_invocation_id": self.operation_invocation_id,
            "shadow_commit_sha": self.shadow_commit_sha,
            "parent_shadow_commit_sha": self.parent_shadow_commit_sha,
            "changed_paths": list(self.changed_paths),
            "reason": self.reason,
        }
