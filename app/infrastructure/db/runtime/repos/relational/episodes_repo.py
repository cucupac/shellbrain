"""This module defines relational repository operations for episodic provenance tables."""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.entities.episodes import (
    Episode,
    EpisodeBuildSnapshot,
    EpisodeEvent,
    EpisodeEventSource,
    EpisodeStatus,
)
from app.core.entities.knowledge_builder import KnowledgeBuildRunStatus
from app.infrastructure.db.runtime.models.knowledge_builder import knowledge_build_runs
from app.core.ports.db.episode_repositories import IEpisodesRepo
from app.infrastructure.db.runtime.models.episodes import episode_events, episodes


class EpisodesRepo(IEpisodesRepo):
    """This class provides persistence operations for episodes and events."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for repository operations."""

        self._session = session

    def create_episode(self, episode: Episode) -> None:
        """This method persists an episode row."""

        self._session.execute(
            episodes.insert().values(
                id=episode.id,
                repo_id=episode.repo_id,
                host_app=episode.host_app,
                thread_id=episode.thread_id,
                status=episode.status.value,
                started_at=episode.started_at or datetime.now(timezone.utc),
                ended_at=episode.ended_at,
                created_at=episode.created_at or datetime.now(timezone.utc),
            )
        )

    def acquire_thread_sync_guard(self, *, repo_id: str, thread_id: str) -> None:
        """This method serializes sync writes for one repo/thread pair."""

        self._session.execute(
            text(
                "SELECT pg_advisory_xact_lock(hashtext(:repo_id), hashtext(:thread_id))"
            ),
            {"repo_id": repo_id, "thread_id": thread_id},
        )

    def get_or_create_episode_for_thread(self, episode: Episode) -> Episode:
        """This method returns the canonical episode row for one thread, creating it when missing."""

        if episode.thread_id is None:
            raise ValueError("thread_id is required when ensuring an episode for sync")
        self._session.execute(
            insert(episodes)
            .values(
                id=episode.id,
                repo_id=episode.repo_id,
                host_app=episode.host_app,
                thread_id=episode.thread_id,
                status=episode.status.value,
                started_at=episode.started_at or datetime.now(timezone.utc),
                ended_at=episode.ended_at,
                created_at=episode.created_at or datetime.now(timezone.utc),
            )
            .on_conflict_do_nothing(index_elements=["repo_id", "thread_id"])
        )
        stored = self.get_episode_by_thread(
            repo_id=episode.repo_id, thread_id=episode.thread_id
        )
        if stored is None:
            raise RuntimeError("episode ensure failed to return a canonical thread row")
        return stored

    def get_episode_by_thread(
        self,
        *,
        repo_id: str,
        thread_id: str,
    ) -> Episode | None:
        """This method fetches one episode by canonical host session key."""

        row = (
            self._session.execute(
                select(episodes).where(
                    episodes.c.repo_id == repo_id,
                    episodes.c.thread_id == thread_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return _to_episode(row)

    def get_episode(
        self,
        *,
        repo_id: str,
        episode_id: str,
    ) -> Episode | None:
        """This method fetches one repo-visible episode by id."""

        row = (
            self._session.execute(
                select(episodes).where(
                    episodes.c.repo_id == repo_id,
                    episodes.c.id == episode_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return _to_episode(row)

    def get_event(
        self,
        *,
        repo_id: str,
        episode_id: str,
        event_id: str,
    ) -> EpisodeEvent | None:
        """This method fetches one repo-visible event by id inside an episode."""

        row = (
            self._session.execute(
                select(episode_events)
                .select_from(
                    episode_events.join(
                        episodes, episode_events.c.episode_id == episodes.c.id
                    )
                )
                .where(
                    episodes.c.repo_id == repo_id,
                    episode_events.c.episode_id == episode_id,
                    episode_events.c.id == event_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return _to_event(row)

    def next_event_seq(self, *, episode_id: str) -> int:
        """This method returns the next append sequence number for one episode."""

        max_seq = self._session.execute(
            select(func.max(episode_events.c.seq)).where(
                episode_events.c.episode_id == episode_id
            )
        ).scalar_one()
        return 1 if max_seq is None else int(max_seq) + 1

    def append_event(self, event: EpisodeEvent) -> None:
        """This method appends an episode event row."""

        self._session.execute(
            episode_events.insert().values(
                id=event.id,
                episode_id=event.episode_id,
                seq=event.seq,
                host_event_key=event.host_event_key,
                source=event.source.value,
                content=event.content,
                created_at=event.created_at or datetime.now(timezone.utc),
            )
        )

    def append_event_if_new(self, event: EpisodeEvent) -> bool:
        """This method appends an episode event only when its host_event_key is new."""

        inserted_id = self._session.execute(
            insert(episode_events)
            .values(
                id=event.id,
                episode_id=event.episode_id,
                seq=event.seq,
                host_event_key=event.host_event_key,
                source=event.source.value,
                content=event.content,
                created_at=event.created_at or datetime.now(timezone.utc),
            )
            .on_conflict_do_nothing(index_elements=["episode_id", "host_event_key"])
            .returning(episode_events.c.id)
        ).scalar_one_or_none()
        return inserted_id is not None

    def list_existing_event_ids(self, *, event_ids: Sequence[str]) -> list[str]:
        """This method returns stored event ids regardless of repo visibility."""

        if not event_ids:
            return []
        rows = self._session.execute(
            select(episode_events.c.id).where(episode_events.c.id.in_(event_ids))
        ).scalars()
        return [str(value) for value in rows]

    def list_visible_event_ids(
        self, *, repo_id: str, event_ids: Sequence[str]
    ) -> list[str]:
        """This method returns stored event ids visible to one repo."""

        if not event_ids:
            return []
        rows = self._session.execute(
            select(episode_events.c.id)
            .select_from(
                episode_events.join(
                    episodes, episode_events.c.episode_id == episodes.c.id
                )
            )
            .where(
                episodes.c.repo_id == repo_id,
                episode_events.c.id.in_(event_ids),
            )
        ).scalars()
        return [str(value) for value in rows]

    def list_recent_events(
        self,
        *,
        repo_id: str,
        episode_id: str,
        limit: int,
    ) -> list[EpisodeEvent]:
        """This method returns recent events for one repo-visible episode ordered newest first."""

        rows = (
            self._session.execute(
                select(episode_events)
                .select_from(
                    episode_events.join(
                        episodes, episode_events.c.episode_id == episodes.c.id
                    )
                )
                .where(
                    episodes.c.repo_id == repo_id,
                    episode_events.c.episode_id == episode_id,
                )
                .order_by(episode_events.c.seq.desc())
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [_to_event(row) for row in rows]

    def list_events_range(
        self,
        *,
        repo_id: str,
        episode_id: str,
        after_seq: int,
        up_to_seq: int,
    ) -> list[EpisodeEvent]:
        """Return one exact event sequence range ordered oldest first."""

        rows = (
            self._session.execute(
                select(episode_events)
                .select_from(
                    episode_events.join(
                        episodes, episode_events.c.episode_id == episodes.c.id
                    )
                )
                .where(
                    episodes.c.repo_id == repo_id,
                    episode_events.c.episode_id == episode_id,
                    episode_events.c.seq > after_seq,
                    episode_events.c.seq <= up_to_seq,
                )
                .order_by(episode_events.c.seq.asc())
            )
            .mappings()
            .all()
        )
        return [_to_event(row) for row in rows]

    def event_watermark(self, *, repo_id: str, episode_id: str) -> int:
        """Return the highest imported event sequence for one repo-visible episode."""

        value = self._session.execute(
            select(func.max(episode_events.c.seq))
            .select_from(
                episode_events.join(
                    episodes, episode_events.c.episode_id == episodes.c.id
                )
            )
            .where(
                episodes.c.repo_id == repo_id,
                episode_events.c.episode_id == episode_id,
            )
        ).scalar_one()
        return 0 if value is None else int(value)

    def list_build_snapshots(self, *, repo_id: str) -> list[EpisodeBuildSnapshot]:
        """Return persisted episode watermarks and latest successful build state."""

        latest_events = (
            select(
                episode_events.c.episode_id.label("episode_id"),
                func.max(episode_events.c.seq).label("latest_event_seq"),
                func.max(episode_events.c.created_at).label("latest_event_at"),
            )
            .group_by(episode_events.c.episode_id)
            .subquery()
        )
        latest_successful_builds = (
            select(
                knowledge_build_runs.c.episode_id.label("episode_id"),
                func.max(knowledge_build_runs.c.event_watermark).label(
                    "latest_successful_build_watermark"
                ),
            )
            .where(
                knowledge_build_runs.c.repo_id == repo_id,
                knowledge_build_runs.c.status.in_(
                    (
                        KnowledgeBuildRunStatus.OK.value,
                        KnowledgeBuildRunStatus.SKIPPED.value,
                    )
                ),
                knowledge_build_runs.c.trigger
                != "explicit_teach",
            )
            .group_by(knowledge_build_runs.c.episode_id)
            .subquery()
        )
        rows = (
            self._session.execute(
                select(
                    episodes.c.id.label("episode_id"),
                    episodes.c.status,
                    latest_events.c.latest_event_seq,
                    latest_events.c.latest_event_at,
                    latest_successful_builds.c.latest_successful_build_watermark,
                )
                .select_from(
                    episodes.join(
                        latest_events,
                        episodes.c.id == latest_events.c.episode_id,
                    ).outerjoin(
                        latest_successful_builds,
                        episodes.c.id
                        == latest_successful_builds.c.episode_id,
                    )
                )
                .where(
                    episodes.c.repo_id == repo_id,
                    episodes.c.status.in_(
                        (EpisodeStatus.ACTIVE.value, EpisodeStatus.CLOSED.value)
                    ),
                )
                .order_by(latest_events.c.latest_event_at.asc(), episodes.c.id.asc())
            )
            .mappings()
            .all()
        )
        return [
            EpisodeBuildSnapshot(
                episode_id=row["episode_id"],
                status=EpisodeStatus(row["status"]),
                latest_event_seq=int(row["latest_event_seq"]),
                latest_event_at=row["latest_event_at"],
                latest_successful_build_watermark=(
                    None
                    if row["latest_successful_build_watermark"] is None
                    else int(row["latest_successful_build_watermark"])
                ),
            )
            for row in rows
        ]


def _to_episode(row) -> Episode:
    return Episode(
        id=row["id"],
        repo_id=row["repo_id"],
        host_app=row["host_app"],
        thread_id=row["thread_id"],
        status=EpisodeStatus(row["status"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        created_at=row["created_at"],
    )


def _to_event(row) -> EpisodeEvent:
    return EpisodeEvent(
        id=row["id"],
        episode_id=row["episode_id"],
        seq=row["seq"],
        host_event_key=row["host_event_key"],
        source=EpisodeEventSource(row["source"]),
        content=row["content"],
        created_at=row["created_at"],
    )
