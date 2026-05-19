"""Request types for the memory add use case."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.entities.ids import EvidenceRefText, MemoryId, RepoId
from app.core.entities.memories import (
    AssociationRelationValue,
    ConfidenceValue,
    EvidenceRefs,
    MemoryKindValue,
    SalienceValue,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _normalize_required_string(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _normalize_memory_id(value: MemoryId, *, field_name: str) -> MemoryId:
    return MemoryId(_normalize_required_string(str(value), field_name=field_name))


def _normalize_repo_id(value: RepoId) -> RepoId:
    return RepoId(_normalize_required_string(str(value), field_name="repo_id"))


class MemoryAddAssociationLink(_StrictModel):
    """Typed explicit association link payload on memory add."""

    to_memory_id: MemoryId
    relation_type: AssociationRelationValue
    confidence: float = Field(ge=0.0, le=1.0)
    salience: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None

    @field_validator("to_memory_id")
    @classmethod
    def _validate_to_memory_id(cls, value: MemoryId) -> MemoryId:
        return _normalize_memory_id(value, field_name="to_memory_id")

    @field_validator("confidence")
    @classmethod
    def _validate_confidence_value(cls, value: float) -> float:
        ConfidenceValue(value)
        return value

    @field_validator("salience")
    @classmethod
    def _validate_salience_value(cls, value: float) -> float:
        SalienceValue(value)
        return value


class MemoryAddLinks(_StrictModel):
    """Optional link payloads on memory-add requests."""

    problem_id: MemoryId | None = None
    related_memory_ids: list[MemoryId] = Field(default_factory=list)
    associations: list[MemoryAddAssociationLink] = Field(default_factory=list)

    @field_validator("problem_id")
    @classmethod
    def _validate_problem_id(cls, value: MemoryId | None) -> MemoryId | None:
        if value is None:
            return value
        return _normalize_memory_id(value, field_name="problem_id")

    @field_validator("related_memory_ids")
    @classmethod
    def _validate_related_unsupported(cls, value: list[MemoryId]) -> list[MemoryId]:
        normalized = [
            _normalize_memory_id(memory_id, field_name="related_memory_ids")
            for memory_id in value
        ]
        if normalized:
            raise ValueError(
                "related_memory_ids is not supported; use associations instead"
            )
        return normalized


class MemoryAddBody(_StrictModel):
    """Memory-add body fields for immutable shellbrain records."""

    text: str
    scope: Literal["repo", "global"]
    kind: MemoryKindValue
    rationale: str | None = None
    links: MemoryAddLinks = Field(default_factory=MemoryAddLinks)
    evidence_refs: list[EvidenceRefText] = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return _normalize_required_string(value, field_name="text")

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(
        cls, value: list[EvidenceRefText]
    ) -> list[EvidenceRefText]:
        normalized = [
            EvidenceRefText(
                _normalize_required_string(str(ref), field_name="evidence_refs")
            )
            for ref in value
        ]
        EvidenceRefs.required(normalized)
        return normalized


class MemoryAddRequest(_StrictModel):
    """Canonical memory-add request payload."""

    op: Literal["create"] = "create"
    repo_id: RepoId
    memory: MemoryAddBody

    @field_validator("repo_id")
    @classmethod
    def _validate_repo_id(cls, value: RepoId) -> RepoId:
        return _normalize_repo_id(value)
