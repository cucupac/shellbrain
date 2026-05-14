"""Core workflow for closing a host episode replaced by a newer session."""

from __future__ import annotations

from datetime import datetime


def close_replaced_episode(
    *,
    repo_id: str,
    host_app: str,
    host_session_key: str,
    ended_at: datetime,
    uow,
) -> str | None:
    """Close the active episode for one replaced host session when present."""

    canonical_thread_id = f"{host_app}:{host_session_key}"
    episode = uow.episodes.get_episode_by_thread(
        repo_id=repo_id, thread_id=canonical_thread_id
    )
    if episode is None:
        return None
    uow.episodes.close_episode(episode_id=episode.id, ended_at=ended_at)
    return episode.id
