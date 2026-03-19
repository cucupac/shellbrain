"""Core session-state entities for per-caller working memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SessionStateResetReason(str, Enum):
    """Reasons a working session may be reset while preserving caller identity metadata."""

    IDLE_EXPIRED = "idle_expired"
    CALLER_SWITCHED = "caller_switched"


@dataclass(kw_only=True)
class SessionState:
    """Per-caller repo-local working state used to drive exact events and guidance."""

    caller_id: str
    host_app: str
    host_session_key: str
    agent_key: str | None = None
    session_started_at: str
    last_seen_at: str
    current_problem_id: str | None = None
    last_events_episode_id: str | None = None
    last_events_event_ids: list[str] = field(default_factory=list)
    last_events_at: str | None = None
    last_guidance_at: str | None = None
    last_guidance_problem_id: str | None = None
