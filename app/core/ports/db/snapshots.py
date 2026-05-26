"""Persistence ports for shadow snapshots and solution deltas."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.entities.snapshots import ShadowSnapshot, SolutionDelta


class ISnapshotsRepo(ABC):
    """Persistence behavior for code-evidence snapshots."""

    @abstractmethod
    def latest_snapshot(self, *, repo_id: str, repo_root: str) -> ShadowSnapshot | None:
        """Return the newest shadow snapshot for one repo root."""

    @abstractmethod
    def latest_snapshot_at_or_before_event(
        self,
        *,
        repo_id: str,
        repo_root: str,
        episode_id: str,
        event_seq: int,
    ) -> ShadowSnapshot | None:
        """Return the latest valid base snapshot for an episode event boundary."""

    @abstractmethod
    def latest_snapshot_in_event_window(
        self,
        *,
        repo_id: str,
        repo_root: str,
        episode_id: str,
        opened_event_seq: int,
        closed_event_seq: int,
    ) -> ShadowSnapshot | None:
        """Return the latest valid final snapshot captured in a scenario window."""

    @abstractmethod
    def get_solution_delta_for_problem_run(
        self, *, problem_run_id: str
    ) -> SolutionDelta | None:
        """Return an existing delta for one problem run."""

    @abstractmethod
    def add_snapshot(self, snapshot: ShadowSnapshot) -> None:
        """Persist one shadow snapshot metadata row."""

    @abstractmethod
    def add_solution_delta(self, delta: SolutionDelta) -> None:
        """Persist one solution delta metadata row."""
