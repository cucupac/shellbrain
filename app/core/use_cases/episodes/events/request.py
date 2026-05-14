"""Request types for the episode events use case."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.entities.ids import RepoId


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EpisodeEventsRequest(_StrictModel):
    """Canonical episode-events request payload."""

    op: Literal["events"] = "events"
    repo_id: RepoId
    limit: int = Field(default=20, ge=1, le=100)
    episode_id: str | None = Field(default=None, min_length=1)
    after_seq: int | None = Field(default=None, ge=0)
    up_to_seq: int | None = Field(default=None, ge=1)
    order: Literal["newest_first", "oldest_first"] = "newest_first"

    @model_validator(mode="after")
    def _validate_event_range(self) -> "EpisodeEventsRequest":
        """Require exact episode selection and a closed upper bound for ranges."""

        has_range = self.after_seq is not None or self.up_to_seq is not None
        if not has_range:
            return self
        if self.episode_id is None:
            raise ValueError("episode_id is required when using event sequence range")
        if self.up_to_seq is None:
            raise ValueError("up_to_seq is required when using event sequence range")
        after_seq = self.after_seq if self.after_seq is not None else 0
        if self.up_to_seq <= after_seq:
            raise ValueError("up_to_seq must be greater than after_seq")
        return self
