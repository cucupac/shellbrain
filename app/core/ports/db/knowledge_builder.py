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
        input_tokens: int | None,
        output_tokens: int | None,
        reasoning_output_tokens: int | None,
        cached_input_tokens_total: int | None,
        cache_read_input_tokens: int | None,
        cache_creation_input_tokens: int | None,
        capture_quality: str | None,
        run_summary: str | None,
        error_code: str | None,
        error_message: str | None,
        finished_at: datetime,
        read_trace: dict[str, object] | None = None,
        code_trace: dict[str, object] | None = None,
    ) -> None:
        """Finalize one previously-running build_knowledge run."""
