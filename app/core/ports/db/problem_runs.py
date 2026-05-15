"""Repository ports for explicit problem-run scenario windows."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.entities.scenarios import ProblemRun


class IProblemRunsRepo(ABC):
    """Persistence behavior for bounded problem-solving scenario records."""

    @abstractmethod
    def get_by_scenario_key(
        self,
        *,
        repo_id: str,
        episode_id: str,
        problem_memory_id: str,
        opened_event_id: str,
    ) -> ProblemRun | None:
        """Return the existing scenario row for one natural idempotency key."""

    @abstractmethod
    def add(self, run: ProblemRun) -> None:
        """Append one explicit problem-run scenario window."""
