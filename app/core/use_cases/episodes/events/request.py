"""Request types for the episode events use case."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.entities.ids import RepoId


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EpisodeEventsRequest(_StrictModel):
    """Canonical episode-events request payload."""

    op: Literal["events"] = "events"
    repo_id: RepoId
    limit: int = Field(default=20, ge=1, le=100)
