"""Request types for syncing one normalized host episode."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NormalizedEpisodeEvent(BaseModel):
    """Typed normalized host event plus provider-specific normalized fields."""

    model_config = ConfigDict(extra="allow")

    host_event_key: str = Field(min_length=1)
    source: Literal["user", "assistant", "tool", "system"]
    occurred_at: str = ""

    @field_validator("host_event_key")
    @classmethod
    def _validate_host_event_key(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("host_event_key must be non-empty")
        return normalized


class SyncEpisodeRequest(_StrictModel):
    """Canonical sync request for one already-normalized host session."""

    repo_id: str
    host_app: str
    host_session_key: str
    thread_id: str
    transcript_path: str
    normalized_events: tuple[NormalizedEpisodeEvent, ...]
