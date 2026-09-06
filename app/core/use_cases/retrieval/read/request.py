"""Request types for the memory read use case."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.entities.ids import RepoId
from app.core.entities.memories import MemoryKindValue


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _normalize_required_string(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _normalize_repo_id(value: RepoId) -> RepoId:
    return RepoId(_normalize_required_string(str(value), field_name="repo_id"))


class ReadConceptsExpandRequest(_StrictModel):
    """Concept-context expansion controls for read requests."""

    mode: Literal["auto", "none"] = "auto"
    max_auto: int = Field(default=2, ge=1, le=6)


class ReadExpandRequest(_StrictModel):
    """Expansion knobs for read requests."""

    concepts: ReadConceptsExpandRequest = Field(
        default_factory=ReadConceptsExpandRequest
    )


class MemoryReadRequest(_StrictModel):
    """Canonical read request payload."""

    op: Literal["read"] = "read"
    repo_id: RepoId
    mode: Literal["ambient", "targeted"] = "targeted"
    query: str = Field(min_length=1)
    include_global: bool = True
    kinds: list[MemoryKindValue] | None = Field(default=None, min_length=1)
    limit: int = Field(default=8, ge=1, le=100)
    expand: ReadExpandRequest = Field(default_factory=ReadExpandRequest)

    @field_validator("repo_id")
    @classmethod
    def _validate_repo_id(cls, value: RepoId) -> RepoId:
        return _normalize_repo_id(value)

    @field_validator("query")
    @classmethod
    def _validate_query(cls, value: str) -> str:
        return _normalize_required_string(value, field_name="query")

    @field_validator("kinds")
    @classmethod
    def _validate_kinds_unique(
        cls,
        value: list[MemoryKindValue] | None,
    ) -> list[MemoryKindValue] | None:
        if value is None:
            return value
        if len(value) != len(set(value)):
            raise ValueError("kinds must be unique")
        return value
