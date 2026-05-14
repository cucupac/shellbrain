"""Entities for knowledge-builder lifecycle tracking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class KnowledgeBuildTrigger(str, Enum):
    """Episode lifecycle events that can trigger build_knowledge."""

    SESSION_REPLACED = "session_replaced"
    IDLE_STABLE = "idle_stable"


class KnowledgeBuildRunStatus(str, Enum):
    """Durable statuses for one build_knowledge run."""

    RUNNING = "running"
    OK = "ok"
    SKIPPED = "skipped"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"
    ERROR = "error"


@dataclass(frozen=True, kw_only=True)
class KnowledgeBuildRun:
    """One durable build_knowledge run record."""

    id: str
    repo_id: str
    episode_id: str
    trigger: KnowledgeBuildTrigger
    status: KnowledgeBuildRunStatus
    event_watermark: int
    previous_event_watermark: int | None
    provider: str
    model: str
    reasoning: str
    write_count: int = 0
    skipped_item_count: int = 0
    run_summary: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        """Keep invalid run records from crossing the core boundary."""

        for field_name in ("id", "repo_id", "episode_id", "provider", "model"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.event_watermark < 0:
            raise ValueError("event_watermark must be non-negative")
        if (
            self.previous_event_watermark is not None
            and self.previous_event_watermark < 0
        ):
            raise ValueError("previous_event_watermark must be non-negative")
        if self.write_count < 0:
            raise ValueError("write_count must be non-negative")
        if self.skipped_item_count < 0:
            raise ValueError("skipped_item_count must be non-negative")
