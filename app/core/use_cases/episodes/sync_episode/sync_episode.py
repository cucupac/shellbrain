"""Synchronize normalized host transcript events into episodic tables."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from app.core.entities.episodes import (
    Episode,
    EpisodeEvent,
    EpisodeEventSource,
    EpisodeStatus,
)
from app.core.policies.episodes.event_content import (
    serialize_normalized_episode_event,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.system.clock import IClock
from app.core.ports.system.idgen import IIdGenerator
from app.core.use_cases.episodes.sync_episode.request import (
    NormalizedEpisodeEvent,
    SyncEpisodeRequest,
)
from app.core.use_cases.episodes.sync_episode.result import SyncEpisodeResult


def sync_episode(
    request: SyncEpisodeRequest,
    *,
    uow: IUnitOfWork,
    clock: IClock,
    id_generator: IIdGenerator,
) -> SyncEpisodeResult:
    """Import one already-normalized host transcript into episodes and events."""

    counts = _count_normalized_events(request.normalized_events)
    now = clock.now()
    uow.episodes.acquire_thread_sync_guard(
        repo_id=request.repo_id, thread_id=request.thread_id
    )
    imported_count = 0
    started_at = _earliest_event_timestamp(
        request.normalized_events, fallback=now
    ) or now
    episode = uow.episodes.get_or_create_episode_for_thread(
        Episode(
            id=id_generator.new_id(),
            repo_id=request.repo_id,
            host_app=request.host_app,
            thread_id=request.thread_id,
            status=EpisodeStatus.ACTIVE,
            started_at=started_at,
            created_at=now,
        )
    )
    next_seq = uow.episodes.next_event_seq(episode_id=episode.id)
    for normalized_event in request.normalized_events:
        created_at = _parse_timestamp(normalized_event.occurred_at, fallback=now)
        source = EpisodeEventSource(normalized_event.source)
        inserted = uow.episodes.append_event_if_new(
            EpisodeEvent(
                id=id_generator.new_id(),
                episode_id=episode.id,
                seq=next_seq,
                host_event_key=normalized_event.host_event_key,
                source=source,
                content=serialize_normalized_episode_event(normalized_event),
                created_at=created_at,
            )
        )
        if not inserted:
            continue
        next_seq += 1
        imported_count += 1

    return SyncEpisodeResult(
        episode_id=episode.id,
        thread_id=request.thread_id,
        imported_event_count=imported_count,
        transcript_path=request.transcript_path,
        total_event_count=int(counts["total_event_count"]),
        user_event_count=int(counts["user_event_count"]),
        assistant_event_count=int(counts["assistant_event_count"]),
        tool_event_count=int(counts["tool_event_count"]),
        system_event_count=int(counts["system_event_count"]),
        tool_type_counts=dict(counts["tool_type_counts"]),
    )


def _parse_timestamp(value: str, *, fallback: datetime) -> datetime:
    """Parse one host timestamp into a timezone-aware datetime."""

    if not value:
        return fallback
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _earliest_event_timestamp(
    events: Sequence[NormalizedEpisodeEvent], *, fallback: datetime
) -> datetime | None:
    """Return the earliest normalized event timestamp if any exist."""

    timestamps = [
        _parse_timestamp(event.occurred_at, fallback=fallback)
        for event in events
        if event.occurred_at
    ]
    if not timestamps:
        return None
    return min(timestamps)


def _count_normalized_events(
    events: Sequence[NormalizedEpisodeEvent],
) -> dict[str, Any]:
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
        if event.source == "user":
            counts["user_event_count"] += 1
        elif event.source == "assistant":
            counts["assistant_event_count"] += 1
        elif event.source == "tool":
            counts["tool_event_count"] += 1
            tool_name = str(event.to_content_dict().get("tool_name") or "unknown_tool")
            tool_type_counts[tool_name] = tool_type_counts.get(tool_name, 0) + 1
        elif event.source == "system":
            counts["system_event_count"] += 1
    return counts
