"""Request types for building snapshot-backed code-delta context."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class CodeDeltaContextRequest:
    """Core request for one bounded episode event window."""

    repo_id: str
    repo_root: str
    episode_id: str
    after_seq: int
    up_to_seq: int

    def __post_init__(self) -> None:
        """Keep event-window boundaries explicit before querying snapshots."""

        for field_name in ("repo_id", "repo_root", "episode_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.after_seq < 0:
            raise ValueError("after_seq must be non-negative")
        if self.up_to_seq <= self.after_seq:
            raise ValueError("up_to_seq must be greater than after_seq")
