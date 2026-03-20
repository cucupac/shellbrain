"""This module defines relational repository operations for utility feedback entries."""

from datetime import datetime, timezone

from app.core.entities.utility import UtilityObservation
from app.core.interfaces.repos import IUtilityRepo
from app.periphery.db.models.utility import utility_observations


class UtilityRepo(IUtilityRepo):
    """This class provides persistence operations for utility observations."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for repository operations."""

        self._session = session

    def append_observation(self, observation: UtilityObservation) -> None:
        """This method appends a utility observation row."""

        self._session.execute(
            utility_observations.insert().values(
                id=observation.id,
                memory_id=observation.memory_id,
                problem_id=observation.problem_id,
                vote=observation.vote,
                rationale=observation.rationale,
                created_at=datetime.now(timezone.utc),
            )
        )
