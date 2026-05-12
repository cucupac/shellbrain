"""Request types for syncing one normalized host episode."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

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

    def to_content_dict(self) -> dict[str, Any]:
        """Return the normalized content payload for episode storage."""

        return self.model_dump(mode="python")


class SyncEpisodeRequest(_StrictModel):
    """Canonical sync request for one already-normalized host session."""

    repo_id: str
    host_app: str
    host_session_key: str
    thread_id: str
    transcript_path: str
    normalized_events: tuple[NormalizedEpisodeEvent, ...]

    @classmethod
    def from_raw_events(
        cls,
        *,
        repo_id: str,
        host_app: str,
        host_session_key: str,
        thread_id: str,
        transcript_path: str,
        normalized_events: Sequence[NormalizedEpisodeEvent | Mapping[str, Any]],
    ) -> "SyncEpisodeRequest":
        """Build a sync request from adapter-produced event mappings."""

        events = tuple(
            event
            if isinstance(event, NormalizedEpisodeEvent)
            else NormalizedEpisodeEvent.model_validate(dict(event))
            for event in normalized_events
        )
        return cls(
            repo_id=repo_id,
            host_app=host_app,
            host_session_key=host_session_key,
            thread_id=thread_id,
            transcript_path=transcript_path,
            normalized_events=events,
        )
