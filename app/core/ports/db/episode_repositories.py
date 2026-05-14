"""Repository ports for episode persistence."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Sequence

from app.core.entities.episodes import Episode, EpisodeEvent, SessionTransfer


class IEpisodesRepo(ABC):
    """This interface defines persistence operations for episodes and events."""

    @abstractmethod
    def create_episode(self, episode: Episode) -> None:
        """This method persists an episode row."""

    @abstractmethod
    def acquire_thread_sync_guard(self, *, repo_id: str, thread_id: str) -> None:
        """This method serializes sync writes for one repo/thread pair."""

    @abstractmethod
    def get_or_create_episode_for_thread(self, episode: Episode) -> Episode:
        """This method returns the canonical episode row for one thread, creating it when missing."""

    @abstractmethod
    def get_episode_by_thread(
        self,
        *,
        repo_id: str,
        thread_id: str,
    ) -> Episode | None:
        """This method fetches one episode by canonical host session key."""

    @abstractmethod
    def get_episode(
        self,
        *,
        repo_id: str,
        episode_id: str,
    ) -> Episode | None:
        """This method fetches one repo-visible episode by id."""

    @abstractmethod
    def list_event_keys(self, *, episode_id: str) -> Sequence[str]:
        """This method returns already-imported upstream event keys for one episode."""

    @abstractmethod
    def next_event_seq(self, *, episode_id: str) -> int:
        """This method returns the next append sequence number for one episode."""

    @abstractmethod
    def append_event(self, event: EpisodeEvent) -> None:
        """This method appends an event into an episode stream."""

    @abstractmethod
    def append_event_if_new(self, event: EpisodeEvent) -> bool:
        """This method appends an event only when its host_event_key is not already present."""

    @abstractmethod
    def close_episode(self, *, episode_id: str, ended_at: datetime) -> None:
        """This method marks an active episode closed."""

    @abstractmethod
    def append_transfer(self, transfer: SessionTransfer) -> None:
        """This method appends a cross-session transfer row."""

    @abstractmethod
    def list_existing_event_ids(self, *, event_ids: Sequence[str]) -> Sequence[str]:
        """This method returns episode-event ids that exist anywhere in storage."""

    @abstractmethod
    def list_visible_event_ids(
        self, *, repo_id: str, event_ids: Sequence[str]
    ) -> Sequence[str]:
        """This method returns episode-event ids visible within one repo."""

    @abstractmethod
    def list_recent_events(
        self,
        *,
        repo_id: str,
        episode_id: str,
        limit: int,
    ) -> Sequence[EpisodeEvent]:
        """This method returns recent events for one visible episode ordered newest first."""

    @abstractmethod
    def list_events_range(
        self,
        *,
        repo_id: str,
        episode_id: str,
        after_seq: int,
        up_to_seq: int,
    ) -> Sequence[EpisodeEvent]:
        """Return visible episode events in (after_seq, up_to_seq] ordered oldest first."""

    @abstractmethod
    def event_watermark(self, *, repo_id: str, episode_id: str) -> int:
        """Return the highest imported event sequence for one repo-visible episode."""
