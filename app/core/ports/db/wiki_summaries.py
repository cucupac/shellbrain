"""Repository port for generated wiki summary cache records."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Sequence

from app.core.entities.wiki_summaries import (
    WikiSummaryInputSnapshot,
    WikiSummaryRecord,
    WikiSummaryTarget,
)


class IWikiSummaryRepo(ABC):
    """Read and write cached generated wiki summaries."""

    @abstractmethod
    def get(self, target: WikiSummaryTarget) -> WikiSummaryRecord | None:
        """Return the cached summary for one target when present."""

    @abstractmethod
    def acquire_refresh(
        self,
        *,
        snapshot: WikiSummaryInputSnapshot,
        model: str,
        prompt_version: str,
        now: datetime,
        stale_running_before: datetime,
    ) -> bool:
        """Mark one target pending when no fresh refresh is already running."""

    @abstractmethod
    def record_success(
        self,
        *,
        snapshot: WikiSummaryInputSnapshot,
        body: str,
        model: str,
        prompt_version: str,
        now: datetime,
    ) -> None:
        """Persist generated summary prose for one target."""

    @abstractmethod
    def record_failure(
        self,
        *,
        snapshot: WikiSummaryInputSnapshot,
        model: str,
        prompt_version: str,
        error_code: str,
        error_message: str,
        now: datetime,
    ) -> None:
        """Persist a failed refresh attempt without deleting prior prose."""

    @abstractmethod
    def list_existing_targets(
        self, *, repo_ids: Sequence[str]
    ) -> Sequence[WikiSummaryTarget]:
        """Return summary targets that already have cache rows for these repos."""
