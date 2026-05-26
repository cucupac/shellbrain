"""Core-owned port for repo-local shadow Git storage."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.entities.snapshots import (
    ShadowGitCaptureRequest,
    ShadowGitCaptureResult,
    ShadowGitDiffResult,
)


class IShadowGitStore(ABC):
    """Filesystem/Git behavior needed by snapshot use cases."""

    @abstractmethod
    def capture_snapshot(
        self, request: ShadowGitCaptureRequest
    ) -> ShadowGitCaptureResult:
        """Capture the current repo tree into shadow Git."""

    @abstractmethod
    def diff_snapshot_pair(
        self, *, repo_root: str, base_commit_sha: str, final_commit_sha: str
    ) -> ShadowGitDiffResult:
        """Return a stable patch hash and changed paths for two shadow commits."""
