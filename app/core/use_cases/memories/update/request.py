"""Request types for the memory update use case."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.entities.ids import EvidenceRefText, MemoryId, RepoId
from app.core.entities.memories import (
    AssociationRelationValue,
    ConfidenceValue,
    EvidenceRefs,
    SalienceValue,
    UtilityVoteValue,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ArchiveStateUpdate(_StrictModel):
    """Archive-state update payload fields."""

    type: Literal["archive_state"]
    archived: bool
    rationale: str | None = None


class UtilityVoteUpdate(_StrictModel):
    """Utility-vote update payload fields."""

    type: Literal["utility_vote"]
    problem_id: MemoryId
    vote: float = Field(ge=-1.0, le=1.0)
    rationale: str | None = None
    evidence_refs: list[EvidenceRefText] = Field(default_factory=list)

    @field_validator("vote")
    @classmethod
    def _validate_vote_value(cls, value: float) -> float:
        UtilityVoteValue(value)
        return value

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(
        cls, value: list[EvidenceRefText]
    ) -> list[EvidenceRefText]:
        EvidenceRefs.optional(value)
        return value


class FactUpdateLinkUpdate(_StrictModel):
    """Fact-update-link payload fields."""

    type: Literal["fact_update_link"]
    old_fact_id: MemoryId
    new_fact_id: MemoryId
    rationale: str | None = None
    evidence_refs: list[EvidenceRefText] = Field(default_factory=list)

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(
        cls, value: list[EvidenceRefText]
    ) -> list[EvidenceRefText]:
        EvidenceRefs.optional(value)
        return value


class AssociationLinkUpdate(_StrictModel):
    """Association-link update payload fields."""

    type: Literal["association_link"]
    to_memory_id: MemoryId
    relation_type: AssociationRelationValue
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    salience: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = None
    evidence_refs: list[EvidenceRefText] = Field(min_length=1)

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

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(
        cls, value: list[EvidenceRefText]
    ) -> list[EvidenceRefText]:
        EvidenceRefs.required(value)
        return value


UpdatePayload = Annotated[
    ArchiveStateUpdate
    | UtilityVoteUpdate
    | FactUpdateLinkUpdate
    | AssociationLinkUpdate,
    Field(discriminator="type"),
]


class MemoryUpdateRequest(_StrictModel):
    """Canonical update request payload."""

    op: Literal["update"] = "update"
    repo_id: RepoId
    memory_id: MemoryId
    update: UpdatePayload


class BatchUtilityVoteItem(_StrictModel):
    """One utility-vote update entry inside a batch update request."""

    memory_id: MemoryId
    update: UtilityVoteUpdate


class MemoryBatchUpdateRequest(_StrictModel):
    """Canonical batch utility-update payload."""

    op: Literal["update"] = "update"
    repo_id: RepoId
    updates: list[BatchUtilityVoteItem] = Field(min_length=1)
