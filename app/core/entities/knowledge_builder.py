"""Entities for knowledge-builder lifecycle tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
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
    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_output_tokens: int | None = None
    cached_input_tokens_total: int | None = None
    cache_read_input_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    capture_quality: str | None = None
    run_summary: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    read_trace: dict[str, object] = field(default_factory=dict)
    code_trace: dict[str, object] = field(default_factory=dict)
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
        for field_name in (
            "input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
            "cached_input_tokens_total",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        if self.capture_quality is not None and self.capture_quality not in {
            "exact",
            "estimated",
        }:
            raise ValueError("capture_quality must be exact or estimated")
        if not isinstance(self.read_trace, dict):
            raise ValueError("read_trace must be a dict")
        if not isinstance(self.code_trace, dict):
            raise ValueError("code_trace must be a dict")
