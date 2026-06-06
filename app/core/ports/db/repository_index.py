"""Repository index read ports."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from app.core.entities.repositories import RepositorySummary


class IRepositoryIndexRepo(ABC):
    """Read-only access to repositories known to Shellbrain."""

    @abstractmethod
    def list_repositories(self) -> Sequence[RepositorySummary]:
        """Return repositories that have Shellbrain knowledge or telemetry rows."""
