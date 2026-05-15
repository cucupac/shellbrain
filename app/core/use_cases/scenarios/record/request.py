"""Request types for recording bounded problem-solving scenarios."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.entities.ids import MemoryId, RepoId
from app.core.entities.scenarios import ScenarioOutcome


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScenarioRecordBody(_StrictModel):
    """Canonical scenario-record body."""

    episode_id: str = Field(min_length=1)
    outcome: ScenarioOutcome
    problem_memory_id: MemoryId
    solution_memory_id: MemoryId | None = None
    opened_event_id: str = Field(min_length=1)
    closed_event_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_solution_by_outcome(self) -> "ScenarioRecordBody":
        """Keep solved and abandoned scenario shapes explicit."""

        if self.outcome == ScenarioOutcome.SOLVED and self.solution_memory_id is None:
            raise ValueError("solved scenarios require solution_memory_id")
        if (
            self.outcome == ScenarioOutcome.ABANDONED
            and self.solution_memory_id is not None
        ):
            raise ValueError("abandoned scenarios must not include solution_memory_id")
        return self


class ScenarioRecordRequest(_StrictModel):
    """Canonical scenario-record request payload."""

    schema_version: Literal["scenario.v1"]
    repo_id: RepoId
    scenario: ScenarioRecordBody
