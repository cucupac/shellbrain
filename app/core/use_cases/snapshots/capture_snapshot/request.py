"""Request types for capturing shadow snapshots."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.entities.snapshots import ShadowSnapshotReason


@dataclass(frozen=True, kw_only=True)
class CaptureSnapshotRequest:
    """Core request to capture one repo state."""

    repo_id: str
    repo_root: str
    reason: ShadowSnapshotReason
    episode_id: str | None = None
    captured_after_event_seq: int | None = None
    operation_invocation_id: str | None = None

    def __post_init__(self) -> None:
        """Keep snapshot capture requests repo-scoped and explicit."""

        for field_name in ("repo_id", "repo_root"):
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
