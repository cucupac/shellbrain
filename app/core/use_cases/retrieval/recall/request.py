"""Request types for the worker-facing recall use case."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.entities.ids import RepoId


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _normalize_required_string(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _normalize_repo_id(value: RepoId) -> RepoId:
    return RepoId(_normalize_required_string(str(value), field_name="repo_id"))


class RecallCurrentProblem(_StrictModel):
    """Required worker problem context for recall synthesis."""

    goal: str = Field(min_length=1)
    surface: str = Field(min_length=1)
    obstacle: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)

    @field_validator("goal", "surface", "obstacle", "hypothesis")
    @classmethod
    def _validate_non_blank(cls, value: str) -> str:
        return _normalize_required_string(value, field_name="current_problem fields")


class MemoryRecallRequest(_StrictModel):
    """Canonical recall request payload."""

    op: Literal["recall"] = "recall"
    repo_id: RepoId
    query: str = Field(min_length=1)
    limit: int | None = Field(default=None, ge=1, le=100)
    current_problem: RecallCurrentProblem

    @field_validator("repo_id")
    @classmethod
    def _validate_repo_id(cls, value: RepoId) -> RepoId:
        return _normalize_repo_id(value)

    @field_validator("query")
    @classmethod
    def _validate_query(cls, value: str) -> str:
        return _normalize_required_string(value, field_name="query")
