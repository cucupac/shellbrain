"""This module defines episodic session entities and transfer provenance entities."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EpisodeStatus(str, Enum):
    """This enum defines lifecycle status values for episodes."""

    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class EpisodeEventSource(str, Enum):
    """This enum defines allowed source values for episode events."""

    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


@dataclass(kw_only=True)
class Episode:
    """This dataclass models a work-session container record."""

    id: str
    repo_id: str
    host_app: str
    thread_id: str | None = None
    title: str | None = None
    objective: str | None = None
    status: EpisodeStatus = EpisodeStatus.ACTIVE
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class EpisodeBuildSnapshot:
    """This dataclass exposes persisted episode state needed for build planning."""

    episode_id: str
    status: EpisodeStatus
    latest_event_seq: int
    latest_event_at: datetime
    latest_successful_build_watermark: int | None = None

    def __post_init__(self) -> None:
        """Reject invalid persisted build-planning state at the core boundary."""

        if not isinstance(self.episode_id, str) or not self.episode_id.strip():
            raise ValueError("episode_id must be a non-empty string")
        if not isinstance(self.status, EpisodeStatus):
            raise ValueError("status must be an EpisodeStatus")
        if self.latest_event_seq < 1:
            raise ValueError("latest_event_seq must be positive")
        if not isinstance(self.latest_event_at, datetime):
            raise ValueError("latest_event_at must be a datetime")
        if (
            self.latest_successful_build_watermark is not None
            and self.latest_successful_build_watermark < 0
        ):
            raise ValueError("latest_successful_build_watermark must be non-negative")


@dataclass(kw_only=True)
class EpisodeEvent:
    """This dataclass models a single immutable event inside an episode."""

    id: str
    episode_id: str
    seq: int
    host_event_key: str
    source: EpisodeEventSource
    content: str
    created_at: datetime | None = None


@dataclass(kw_only=True)
class SessionTransfer:
    """This dataclass models immutable cross-session transfer provenance."""

    id: str
    repo_id: str
    from_episode_id: str
    to_episode_id: str
    event_id: str
    transfer_kind: str
    rationale: str | None = None
    transferred_by: str | None = None
    created_at: datetime | None = None
