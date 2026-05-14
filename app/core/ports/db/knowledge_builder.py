"""Repository ports for knowledge-builder run persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.core.entities.knowledge_builder import (
    KnowledgeBuildRun,
    KnowledgeBuildRunStatus,
)


class IKnowledgeBuildRunsRepo(ABC):
    """Persistence behavior for build_knowledge run records and locks."""

    @abstractmethod
    def acquire_episode_lock(self, *, repo_id: str, episode_id: str) -> bool:
        """Try to acquire a transaction-scoped lock for one repo episode."""

    @abstractmethod
    def latest_successful_watermark(
        self, *, repo_id: str, episode_id: str
    ) -> int | None:
        """Return the newest successfully processed event watermark."""

    @abstractmethod
    def list_running_runs(
        self, *, repo_id: str, episode_id: str
    ) -> tuple[KnowledgeBuildRun, ...]:
        """Return currently-running rows for the episode ordered by start time."""

    @abstractmethod
    def add(self, run: KnowledgeBuildRun) -> None:
        """Append one build_knowledge run record."""

    @abstractmethod
    def complete(
        self,
        *,
        run_id: str,
        status: KnowledgeBuildRunStatus,
        write_count: int,
        skipped_item_count: int,
        run_summary: str | None,
        error_code: str | None,
        error_message: str | None,
        finished_at: datetime,
    ) -> None:
        """Finalize one previously-running build_knowledge run."""
