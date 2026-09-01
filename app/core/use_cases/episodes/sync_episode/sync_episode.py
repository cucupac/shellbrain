"""Synchronize normalized host transcript events into episodic tables."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timezone
import json

from app.core.entities.episodes import (
    Episode,
    EpisodeEvent,
    EpisodeEventSource,
    EpisodeStatus,
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

    source_counts = Counter(event.source for event in request.normalized_events)
    tool_type_counts = Counter(
        str(event.model_dump(mode="python").get("tool_name") or "unknown_tool")
        for event in request.normalized_events
        if event.source == "tool"
    )
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
                content=json.dumps(
                    normalized_event.model_dump(mode="python"),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
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
        total_event_count=len(request.normalized_events),
        user_event_count=source_counts["user"],
        assistant_event_count=source_counts["assistant"],
        tool_event_count=source_counts["tool"],
        system_event_count=source_counts["system"],
        tool_type_counts=dict(tool_type_counts),
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
