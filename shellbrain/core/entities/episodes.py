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
