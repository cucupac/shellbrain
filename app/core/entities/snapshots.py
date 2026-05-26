"""Entities for repo-local shadow snapshots and solution deltas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SnapshotCaptureStatus(str, Enum):
    """Public result states for `shellbrain snapshot`."""

    CREATED = "created"
    NOOP = "noop"
    BASELINE_ONLY = "baseline_only"


class ShadowSnapshotReason(str, Enum):
    """Why one shadow snapshot row exists."""

    BASELINE = "baseline"
    CLOSEOUT = "closeout"
    BASELINE_ONLY = "baseline_only"


class ShadowGitPathChangeStatus(str, Enum):
    """Path-level change statuses reported by shadow Git diffs."""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class CodeDeltaContextStatus(str, Enum):
    """Public availability states for code-delta context."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CodeDeltaUnavailableReason(str, Enum):
    """Expected reasons an event window cannot expose code-delta context."""

    MISSING_BASE_SNAPSHOT = "missing_base_snapshot"
    MISSING_FINAL_SNAPSHOT = "missing_final_snapshot"
    BASE_AND_FINAL_SNAPSHOT_MATCH = "base_and_final_snapshot_match"
    BASELINE_ONLY_BASE_SNAPSHOT = "baseline_only_base_snapshot"
    BASELINE_ONLY_FINAL_SNAPSHOT = "baseline_only_final_snapshot"
    EMPTY_DELTA = "empty_delta"


@dataclass(frozen=True, kw_only=True)
class ShadowGitPathChange:
    """One path-level change between two shadow Git commits."""

    status: ShadowGitPathChangeStatus
    path: str
    old_path: str | None = None

    def __post_init__(self) -> None:
        """Keep path-change status and rename metadata honest."""

        if not isinstance(self.status, ShadowGitPathChangeStatus):
            raise ValueError("status must be a ShadowGitPathChangeStatus")
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("path must be a non-empty string")
        if self.status is ShadowGitPathChangeStatus.RENAMED:
            if not isinstance(self.old_path, str) or not self.old_path.strip():
                raise ValueError("old_path is required for renamed paths")
        elif self.old_path is not None:
            raise ValueError("old_path is valid only for renamed paths")

    def to_response_data(self) -> dict[str, str]:
        """Return the stable JSON payload for one path change."""

        data = {"status": self.status.value, "path": self.path}
        if self.old_path is not None:
            data["old_path"] = self.old_path
        return data


@dataclass(frozen=True, kw_only=True)
class ShadowSnapshot:
    """One captured repo state stored in repo-local shadow Git."""

    id: str
    repo_id: str
    repo_root: str
    shadow_commit_sha: str
    changed_paths: tuple[str, ...]
    reason: ShadowSnapshotReason
    parent_shadow_commit_sha: str | None = None
    episode_id: str | None = None
    captured_after_event_seq: int | None = None
    operation_invocation_id: str | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        """Reject malformed snapshot identity before persistence."""

        for field_name in ("id", "repo_id", "repo_root", "shadow_commit_sha"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if not isinstance(self.reason, ShadowSnapshotReason):
            raise ValueError("reason must be a ShadowSnapshotReason")
        if (
            self.captured_after_event_seq is not None
            and self.captured_after_event_seq < 0
        ):
            raise ValueError("captured_after_event_seq must be non-negative")


@dataclass(frozen=True, kw_only=True)
class SolutionDelta:
    """Patch identity linking one solved problem run to concrete code evidence."""

    id: str
    problem_run_id: str
    repo_id: str
    repo_root: str
    base_snapshot_id: str
    final_snapshot_id: str
    patch_sha: str
    changed_paths: tuple[str, ...]
    episode_id: str | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        """Reject invalid delta identity before persistence."""

        for field_name in (
            "id",
            "problem_run_id",
            "repo_id",
            "repo_root",
            "base_snapshot_id",
            "final_snapshot_id",
            "patch_sha",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.base_snapshot_id == self.final_snapshot_id:
            raise ValueError("solution delta requires distinct snapshots")


@dataclass(frozen=True, kw_only=True)
class ShadowGitCaptureRequest:
    """Core request passed to the shadow Git storage port."""

    snapshot_id: str
    repo_id: str
    repo_root: str
    reason: ShadowSnapshotReason
    episode_id: str | None = None
    captured_after_event_seq: int | None = None
    operation_invocation_id: str | None = None


class ShadowGitCaptureState(str, Enum):
    """Storage-level capture result states."""

    CREATED = "created"
    NOOP = "noop"


@dataclass(frozen=True, kw_only=True)
class ShadowGitCaptureResult:
    """Result returned by the shadow Git storage port."""

    state: ShadowGitCaptureState
    shadow_commit_sha: str | None
    parent_shadow_commit_sha: str | None
    changed_paths: tuple[str, ...]
    tree_sha: str | None = None


@dataclass(frozen=True, kw_only=True)
class ShadowGitDiffResult:
    """Patch identity returned by the shadow Git storage port."""

    patch_sha: str
    path_changes: tuple[ShadowGitPathChange, ...]

    def __post_init__(self) -> None:
        """Reject malformed patch identity before core code trusts it."""

        if not isinstance(self.patch_sha, str) or not self.patch_sha.strip():
            raise ValueError("patch_sha must be a non-empty string")
        for change in self.path_changes:
            if not isinstance(change, ShadowGitPathChange):
                raise ValueError(
                    "path_changes must contain ShadowGitPathChange values"
                )

    @property
    def changed_paths(self) -> tuple[str, ...]:
        """Return changed final paths for existing callers and public payloads."""

        return tuple(change.path for change in self.path_changes)


@dataclass(frozen=True, kw_only=True)
class AvailableCodeDeltaContext:
    """Compact code-delta evidence for one bounded event window."""

    base_snapshot_id: str
    final_snapshot_id: str
    base_shadow_commit_sha: str
    final_shadow_commit_sha: str
    patch_sha: str
    path_changes: tuple[ShadowGitPathChange, ...]
    status: CodeDeltaContextStatus = CodeDeltaContextStatus.AVAILABLE

    def __post_init__(self) -> None:
        """Reject invalid available-context states."""

        if self.status is not CodeDeltaContextStatus.AVAILABLE:
            raise ValueError("available code delta context requires available status")
        for field_name in (
            "base_snapshot_id",
            "final_snapshot_id",
            "base_shadow_commit_sha",
            "final_shadow_commit_sha",
            "patch_sha",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.base_snapshot_id == self.final_snapshot_id:
            raise ValueError("code delta context requires distinct snapshots")
        if not self.path_changes:
            raise ValueError("available code delta context requires path changes")
        for change in self.path_changes:
            if not isinstance(change, ShadowGitPathChange):
                raise ValueError(
                    "path_changes must contain ShadowGitPathChange values"
                )

    @property
    def changed_paths(self) -> tuple[str, ...]:
        """Return changed final paths for compact consumers."""

        return tuple(change.path for change in self.path_changes)

    def to_response_data(self) -> dict[str, object]:
        """Return the stable JSON payload for bounded events."""

        return {
            "status": self.status.value,
            "base_snapshot_id": self.base_snapshot_id,
            "final_snapshot_id": self.final_snapshot_id,
            "base_shadow_commit_sha": self.base_shadow_commit_sha,
            "final_shadow_commit_sha": self.final_shadow_commit_sha,
            "patch_sha": self.patch_sha,
            "path_changes": [
                change.to_response_data() for change in self.path_changes
            ],
            "changed_paths": list(self.changed_paths),
        }


@dataclass(frozen=True, kw_only=True)
class UnavailableCodeDeltaContext:
    """Expected absence of code-delta evidence for one event window."""

    reason: CodeDeltaUnavailableReason
    status: CodeDeltaContextStatus = CodeDeltaContextStatus.UNAVAILABLE

    def __post_init__(self) -> None:
        """Reject unavailable-context states without a typed reason."""

        if self.status is not CodeDeltaContextStatus.UNAVAILABLE:
            raise ValueError(
                "unavailable code delta context requires unavailable status"
            )
        if not isinstance(self.reason, CodeDeltaUnavailableReason):
            raise ValueError("reason must be a CodeDeltaUnavailableReason")

    def to_response_data(self) -> dict[str, str]:
        """Return the stable JSON payload for bounded events."""

        return {"status": self.status.value, "reason": self.reason.value}


CodeDeltaContext = AvailableCodeDeltaContext | UnavailableCodeDeltaContext
