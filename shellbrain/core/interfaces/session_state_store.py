"""Storage interface for repo-local per-caller working state."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from shellbrain.core.entities.session_state import SessionState


class ISessionStateStore(ABC):
    """Abstract persistence for repo-local session state."""

    @abstractmethod
    def load(self, *, repo_root: Path, caller_id: str) -> SessionState | None:
        """Load one caller state when it exists."""

    @abstractmethod
    def save(self, *, repo_root: Path, state: SessionState) -> None:
        """Persist one caller state."""

    @abstractmethod
    def delete(self, *, repo_root: Path, caller_id: str) -> None:
        """Delete one caller state if it exists."""

    @abstractmethod
    def list(self, *, repo_root: Path) -> Sequence[SessionState]:
        """Return all caller states for one repo root."""

    @abstractmethod
    def gc(self, *, repo_root: Path, older_than_iso: str) -> list[str]:
        """Delete caller states last seen before the given cutoff and return deleted caller ids."""
