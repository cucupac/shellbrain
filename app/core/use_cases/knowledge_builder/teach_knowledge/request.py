"""Request types for explicit user teaching."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TeachCurrentProblem(_StrictModel):
    """Structured task context attached to one teaching event."""

    goal: str = Field(min_length=1)
    surface: str = Field(min_length=1)
    obstacle: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)

    @field_validator("goal", "surface", "obstacle", "hypothesis")
    @classmethod
    def _validate_non_blank(cls, value: str) -> str:
        """Require meaningful context strings."""

        text = value.strip()
        if not text:
            raise ValueError("value must be non-empty")
        return text


class TeachKnowledgeRequest(_StrictModel):
    """Core request to turn explicit user teaching into durable knowledge."""

    repo_id: str = Field(min_length=1)
    repo_root: str = Field(min_length=1)
    text: str = Field(min_length=1)
    current_problem: TeachCurrentProblem

    @field_validator("repo_id", "repo_root", "text")
    @classmethod
    def _validate_non_blank(cls, value: str) -> str:
        """Require explicit non-blank strings."""

        text = value.strip()
        if not text:
            raise ValueError("value must be non-empty")
        return text
