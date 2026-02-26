"""This module defines relational repository operations for episodic provenance tables."""

from app.core.entities.episodes import Episode, EpisodeEvent, SessionTransfer
from app.core.interfaces.repos import IEpisodesRepo


class EpisodesRepo(IEpisodesRepo):
    """This class provides persistence operations for episodes, events, and transfers."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for repository operations."""

        self._session = session

    def create_episode(self, episode: Episode) -> None:
        """This method persists an episode row."""

        # TODO: Implement insert into episodes.
        _ = episode

    def append_event(self, event: EpisodeEvent) -> None:
        """This method appends an episode event row."""

        # TODO: Implement insert into episode_events.
        _ = event

    def append_transfer(self, transfer: SessionTransfer) -> None:
        """This method appends a session transfer row."""

        # TODO: Implement insert into session_transfers.
        _ = transfer
