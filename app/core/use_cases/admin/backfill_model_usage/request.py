"""Request types for model-usage backfill."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LinkedModelUsageSession:
    """One Shellbrain-linked host session eligible for usage extraction."""

    repo_id: str
    host_app: str
    host_session_key: str
    thread_id: str | None
    episode_id: str | None
    transcript_path: str


@dataclass(frozen=True)
class BackfillModelUsageRequest:
    """Canonical model-usage backfill request."""

    sessions: tuple[LinkedModelUsageSession, ...]
