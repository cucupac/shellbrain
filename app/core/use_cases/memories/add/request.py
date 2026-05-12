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


class MemoryAddAssociationLink(_StrictModel):
    """Typed explicit association link payload on memory add."""

    to_memory_id: MemoryId
    relation_type: AssociationRelationValue
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    salience: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = None

    @field_validator("confidence")
    @classmethod
    def _validate_confidence_value(cls, value: float | None) -> float | None:
        if value is not None:
            ConfidenceValue(value)
        return value

    @field_validator("salience")
    @classmethod
    def _validate_salience_value(cls, value: float | None) -> float | None:
        if value is not None:
            SalienceValue(value)
        return value


class MemoryAddLinks(_StrictModel):
    """Optional link payloads on memory-add requests."""

    problem_id: MemoryId | None = None
    related_memory_ids: list[MemoryId] = Field(default_factory=list)
    associations: list[MemoryAddAssociationLink] = Field(default_factory=list)

    @field_validator("related_memory_ids")
    @classmethod
    def _validate_related_unique(cls, value: list[MemoryId]) -> list[MemoryId]:
        if len(value) != len(set(value)):
            raise ValueError("related_memory_ids must be unique")
        return value


class MemoryAddBody(_StrictModel):
    """Memory-add body fields for immutable shellbrain records."""

    text: str
    scope: Literal["repo", "global"]
    kind: MemoryKindValue
    rationale: str | None = None
    links: MemoryAddLinks = Field(default_factory=MemoryAddLinks)
    evidence_refs: list[EvidenceRefText] = Field(min_length=1)

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(
        cls, value: list[EvidenceRefText]
    ) -> list[EvidenceRefText]:
        EvidenceRefs.required(value)
        return value


class MemoryAddRequest(_StrictModel):
    """Canonical memory-add request payload."""

    op: Literal["create"] = "create"
    repo_id: RepoId
    memory: MemoryAddBody
