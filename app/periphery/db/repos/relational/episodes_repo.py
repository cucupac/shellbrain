"""This module defines relational repository operations for episodic provenance tables."""

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.core.entities.episodes import Episode, EpisodeEvent, EpisodeEventSource, EpisodeStatus, SessionTransfer
from app.core.interfaces.repos import IEpisodesRepo
from app.periphery.db.models.episodes import episode_events, episodes, session_transfers


class EpisodesRepo(IEpisodesRepo):
    """This class provides persistence operations for episodes, events, and transfers."""

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
                title=episode.title,
                objective=episode.objective,
                status=episode.status.value,
                started_at=episode.started_at or datetime.now(timezone.utc),
                ended_at=episode.ended_at,
                created_at=episode.created_at or datetime.now(timezone.utc),
            )
        )

    def acquire_thread_sync_guard(self, *, repo_id: str, thread_id: str) -> None:
        """This method serializes sync writes for one repo/thread pair."""

        self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:repo_id), hashtext(:thread_id))"),
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
                title=episode.title,
                objective=episode.objective,
                status=episode.status.value,
                started_at=episode.started_at or datetime.now(timezone.utc),
                ended_at=episode.ended_at,
                created_at=episode.created_at or datetime.now(timezone.utc),
            )
            .on_conflict_do_nothing(index_elements=["repo_id", "thread_id"])
        )
        stored = self.get_episode_by_thread(repo_id=episode.repo_id, thread_id=episode.thread_id)
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
        return Episode(
            id=row["id"],
            repo_id=row["repo_id"],
            host_app=row["host_app"],
            thread_id=row["thread_id"],
            title=row["title"],
            objective=row["objective"],
            status=EpisodeStatus(row["status"]),
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            created_at=row["created_at"],
        )

    def list_event_keys(self, *, episode_id: str) -> list[str]:
        """This method returns already-imported upstream event keys for one episode."""

        rows = self._session.execute(
            select(episode_events.c.host_event_key).where(episode_events.c.episode_id == episode_id)
        ).scalars()
        return [str(value) for value in rows]

    def next_event_seq(self, *, episode_id: str) -> int:
        """This method returns the next append sequence number for one episode."""

        max_seq = self._session.execute(
            select(func.max(episode_events.c.seq)).where(episode_events.c.episode_id == episode_id)
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

    def close_episode(self, *, episode_id: str, ended_at: datetime) -> None:
        """This method marks an active episode closed."""

        self._session.execute(
            update(episodes)
            .where(episodes.c.id == episode_id)
            .values(status="closed", ended_at=ended_at)
        )

    def append_transfer(self, transfer: SessionTransfer) -> None:
        """This method appends a session transfer row."""

        self._session.execute(
            session_transfers.insert().values(
                id=transfer.id,
                repo_id=transfer.repo_id,
                from_episode_id=transfer.from_episode_id,
                to_episode_id=transfer.to_episode_id,
                event_id=transfer.event_id,
                transfer_kind=transfer.transfer_kind,
                rationale=transfer.rationale,
                transferred_by=transfer.transferred_by,
                created_at=transfer.created_at or datetime.now(timezone.utc),
            )
        )

    def list_existing_event_ids(self, *, event_ids: Sequence[str]) -> list[str]:
        """This method returns stored event ids regardless of repo visibility."""

        if not event_ids:
            return []
        rows = self._session.execute(
            select(episode_events.c.id).where(episode_events.c.id.in_(event_ids))
        ).scalars()
        return [str(value) for value in rows]

    def list_visible_event_ids(self, *, repo_id: str, event_ids: Sequence[str]) -> list[str]:
        """This method returns stored event ids visible to one repo."""

        if not event_ids:
            return []
        rows = self._session.execute(
            select(episode_events.c.id)
            .select_from(episode_events.join(episodes, episode_events.c.episode_id == episodes.c.id))
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
                .select_from(episode_events.join(episodes, episode_events.c.episode_id == episodes.c.id))
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
        return [
            EpisodeEvent(
                id=row["id"],
                episode_id=row["episode_id"],
                seq=row["seq"],
                host_event_key=row["host_event_key"],
                source=EpisodeEventSource(row["source"]),
                content=row["content"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
