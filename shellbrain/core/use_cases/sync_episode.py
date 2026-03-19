"""Synchronize normalized host transcript events into the episodic provenance tables."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from shellbrain.core.entities.episodes import Episode, EpisodeEvent, EpisodeEventSource, EpisodeStatus
from shellbrain.core.interfaces.unit_of_work import IUnitOfWork


def sync_episode(
    *,
    repo_id: str,
    host_app: str,
    host_session_key: str,
    thread_id: str,
    transcript_path: str,
    normalized_events: Sequence[dict[str, Any]],
    uow: IUnitOfWork,
) -> dict[str, Any]:
    """Import one already-normalized host transcript into episodes and episode events."""

    counts = _count_normalized_events(normalized_events)
    episode = uow.episodes.get_episode_by_thread(repo_id=repo_id, thread_id=thread_id)
    imported_count = 0

    if episode is None:
        started_at = _earliest_event_timestamp(normalized_events) or datetime.now(timezone.utc)
        episode = Episode(
            id=str(uuid4()),
            repo_id=repo_id,
            host_app=host_app,
            thread_id=thread_id,
            status=EpisodeStatus.ACTIVE,
            started_at=started_at,
            created_at=datetime.now(timezone.utc),
        )
        uow.episodes.create_episode(episode)

    existing_keys = set(uow.episodes.list_event_keys(episode_id=episode.id))
    next_seq = uow.episodes.next_event_seq(episode_id=episode.id)
    for normalized_event in normalized_events:
        host_event_key = str(normalized_event["host_event_key"])
        if host_event_key in existing_keys:
            continue
        created_at = _parse_timestamp(str(normalized_event["occurred_at"]))
        source = EpisodeEventSource(str(normalized_event["source"]))
        uow.episodes.append_event(
            EpisodeEvent(
                id=str(uuid4()),
                episode_id=episode.id,
                seq=next_seq,
                host_event_key=host_event_key,
                source=source,
                content=json.dumps(normalized_event),
                created_at=created_at,
            )
        )
        existing_keys.add(host_event_key)
        next_seq += 1
        imported_count += 1

    return {
        "episode_id": episode.id,
        "thread_id": thread_id,
        "imported_event_count": imported_count,
        "transcript_path": transcript_path,
        "total_event_count": counts["total_event_count"],
        "user_event_count": counts["user_event_count"],
        "assistant_event_count": counts["assistant_event_count"],
        "tool_event_count": counts["tool_event_count"],
        "system_event_count": counts["system_event_count"],
        "tool_type_counts": counts["tool_type_counts"],
    }


def sync_episode_from_host(
    *,
    repo_id: str,
    host_app: str,
    host_session_key: str,
    uow: IUnitOfWork,
    search_roots,
    last_known_path=None,
) -> dict[str, Any]:
    """Backward-compatible host sync wrapper used by existing callers."""

    from shellbrain.periphery.episodes.normalization import normalize_host_transcript
    from shellbrain.periphery.episodes.source_discovery import resolve_host_transcript_source

    transcript_path = resolve_host_transcript_source(
        host_app=host_app,
        host_session_key=host_session_key,
        search_roots=search_roots,
        last_known_path=last_known_path,
    )
    normalized_events = normalize_host_transcript(
        host_app=host_app,
        host_session_key=host_session_key,
        transcript_path=transcript_path,
    )
    return sync_episode(
        repo_id=repo_id,
        host_app=host_app,
        host_session_key=host_session_key,
        thread_id=f"{host_app}:{host_session_key}",
        transcript_path=str(transcript_path),
        normalized_events=normalized_events,
        uow=uow,
    )


def _parse_timestamp(value: str) -> datetime:
    """Parse one host timestamp into a timezone-aware datetime."""

    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _earliest_event_timestamp(events: Sequence[dict[str, Any]]) -> datetime | None:
    """Return the earliest normalized event timestamp if any exist."""

    timestamps = [
        _parse_timestamp(str(event["occurred_at"]))
        for event in events
        if event.get("occurred_at")
    ]
    if not timestamps:
        return None
    return min(timestamps)


def _count_normalized_events(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Compute telemetry-friendly source and tool-type counts from normalized events."""

    tool_type_counts: dict[str, int] = {}
    counts = {
        "total_event_count": len(events),
        "user_event_count": 0,
        "assistant_event_count": 0,
        "tool_event_count": 0,
        "system_event_count": 0,
        "tool_type_counts": tool_type_counts,
    }
    for event in events:
        source = str(event.get("source") or "")
        if source == "user":
            counts["user_event_count"] += 1
        elif source == "assistant":
            counts["assistant_event_count"] += 1
        elif source == "tool":
            counts["tool_event_count"] += 1
            tool_name = str(event.get("tool_name") or "unknown_tool")
            tool_type_counts[tool_name] = tool_type_counts.get(tool_name, 0) + 1
        elif source == "system":
            counts["system_event_count"] += 1
    return counts
