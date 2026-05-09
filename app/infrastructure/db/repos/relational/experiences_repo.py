"""This module defines relational repository operations for experiential links."""

from datetime import datetime, timezone

from app.core.entities.facts import FactUpdate, ProblemAttempt
from app.core.ports.memory_repositories import IExperiencesRepo
from app.infrastructure.db.models.experiences import fact_updates, problem_attempts


class ExperiencesRepo(IExperiencesRepo):
    """This class provides persistence operations for problem attempts and fact updates."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for repository operations."""

        self._session = session

    def create_problem_attempt(self, attempt: ProblemAttempt) -> None:
        """This method persists a problem-attempt link row."""

        self._session.execute(
            problem_attempts.insert().values(
                problem_id=attempt.problem_id,
                attempt_id=attempt.attempt_id,
                role=attempt.role.value,
                created_at=datetime.now(timezone.utc),
            )
        )

    def create_fact_update(self, fact_update: FactUpdate) -> None:
        """This method persists a fact-update chain row."""

        self._session.execute(
            fact_updates.insert().values(
                id=fact_update.id,
                old_fact_id=fact_update.old_fact_id,
                change_id=fact_update.change_id,
                new_fact_id=fact_update.new_fact_id,
                created_at=datetime.now(timezone.utc),
            )
        )
