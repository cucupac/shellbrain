"""Strict request contracts for episode operations."""

from typing import Literal

from pydantic import Field

from app.core.contracts.base import StrictBaseModel
from app.core.entities.ids import RepoId


class EpisodeEventsRequest(StrictBaseModel):
    """Canonical episode-events request payload."""

    op: Literal["events"] = "events"
    repo_id: RepoId
    limit: int = Field(default=20, ge=1, le=100)
