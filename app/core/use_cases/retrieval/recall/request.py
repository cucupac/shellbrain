"""Request types for the worker-facing recall use case."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.entities.ids import RepoId


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecallCurrentProblem(_StrictModel):
    """Optional worker problem context for recall synthesis."""

    goal: str | None = Field(default=None, min_length=1)
    surface: str | None = Field(default=None, min_length=1)
    obstacle: str | None = Field(default=None, min_length=1)
    hypothesis: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_any_context(self) -> "RecallCurrentProblem":
        if not any((self.goal, self.surface, self.obstacle, self.hypothesis)):
            raise ValueError("current_problem must include at least one field")
        return self


class MemoryRecallRequest(_StrictModel):
    """Canonical recall request payload."""

    op: Literal["recall"] = "recall"
    repo_id: RepoId
    query: str = Field(min_length=1)
    limit: int | None = Field(default=None, ge=1, le=100)
    current_problem: RecallCurrentProblem | None = None
