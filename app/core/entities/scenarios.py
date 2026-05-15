"""Scenario entities for bounded problem-solving run windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ScenarioOutcome(str, Enum):
    """Agent-facing terminal outcomes for one problem-solving scenario."""

    SOLVED = "solved"
    ABANDONED = "abandoned"


class ProblemRunStatus(str, Enum):
    """Durable storage statuses for explicit problem-run windows."""

    OPEN = "open"
    CLOSED = "closed"
    ABANDONED = "abandoned"


@dataclass(frozen=True, kw_only=True)
class ProblemRun:
    """One bounded problem-solving scenario stored for token/ROI analysis."""

    id: str
    repo_id: str
    status: ProblemRunStatus
    opened_at: datetime
    opened_by: str
    thread_id: str | None = None
    host_app: str | None = None
    host_session_key: str | None = None
    episode_id: str | None = None
    opened_event_id: str | None = None
    closed_at: datetime | None = None
    closed_by: str | None = None
    closed_event_id: str | None = None
    problem_memory_id: str | None = None
    solution_memory_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        """Keep invalid run windows from crossing core boundaries."""

        for field_name in ("id", "repo_id", "opened_by"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if self.status == ProblemRunStatus.OPEN and self.closed_at is not None:
            raise ValueError("open problem runs cannot have closed_at")
        if self.status != ProblemRunStatus.OPEN and self.closed_at is None:
            raise ValueError("closed problem runs require closed_at")
        if self.closed_at is not None and self.closed_at < self.opened_at:
            raise ValueError("closed_at must be greater than or equal to opened_at")


def outcome_to_problem_run_status(outcome: ScenarioOutcome) -> ProblemRunStatus:
    """Map the agent-facing scenario outcome to durable run status."""

    if outcome == ScenarioOutcome.SOLVED:
        return ProblemRunStatus.CLOSED
    return ProblemRunStatus.ABANDONED
