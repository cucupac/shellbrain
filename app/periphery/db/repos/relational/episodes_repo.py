"""This module defines relational repository operations for episodic provenance tables."""

from datetime import datetime, timezone

from sqlalchemy import func, select, update

from app.core.entities.episodes import Episode, EpisodeEvent, EpisodeStatus, SessionTransfer
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
