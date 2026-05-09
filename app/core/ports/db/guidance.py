"""Ports for guidance queries consumed by core use cases."""

from abc import ABC, abstractmethod
from typing import Sequence

from app.core.entities.guidance import PendingUtilityCandidate


class IPendingUtilityCandidatesRepo(ABC):
    """This interface defines the query needed to remind agents about missing utility votes."""

    @abstractmethod
    def list_pending_utility_candidates(
        self,
        *,
        repo_id: str,
        caller_id: str,
        problem_id: str,
        since_iso: str,
    ) -> Sequence[PendingUtilityCandidate]:
        """This method returns retrieved memories that still lack a utility vote for one problem."""
