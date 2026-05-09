"""This module defines strict internal request contracts for memory and episode operations."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.entities.ids import EvidenceRefText, MemoryId, RepoId
from app.core.entities.memories import (
    ConfidenceValue,
    EvidenceRefs,
    SalienceValue,
    UtilityVoteValue,
)


MemoryKindValue = Literal[
    "problem", "solution", "failed_tactic", "fact", "preference", "change", "frontier"
]
AssociationRelationValue = Literal["depends_on", "associated_with", "matures_into"]


class StrictBaseModel(BaseModel):
    """This base model enforces strict schemas by rejecting unknown fields."""

    model_config = ConfigDict(extra="forbid")


class EpisodeEventsRequest(StrictBaseModel):
    """This model defines the canonical episode-events request payload."""

    op: Literal["events"] = "events"
    repo_id: RepoId
    limit: int = Field(default=20, ge=1, le=100)


class MemoryCreateAssociationLink(StrictBaseModel):
    """This model defines a typed explicit association link payload on create."""

    to_memory_id: MemoryId
    relation_type: AssociationRelationValue
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    salience: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = None

    @field_validator("confidence")
    @classmethod
    def _validate_confidence_value(cls, value: float | None) -> float | None:
        """Validate confidence through the memory-domain value object."""

        if value is not None:
            ConfidenceValue(value)
        return value

    @field_validator("salience")
    @classmethod
    def _validate_salience_value(cls, value: float | None) -> float | None:
        """Validate salience through the memory-domain value object."""

        if value is not None:
            SalienceValue(value)
        return value


class MemoryCreateLinks(StrictBaseModel):
    """This model defines optional link payloads on create requests."""

    problem_id: MemoryId | None = None
    related_memory_ids: list[MemoryId] = Field(default_factory=list)
    associations: list[MemoryCreateAssociationLink] = Field(default_factory=list)

    @field_validator("related_memory_ids")
    @classmethod
    def _validate_related_unique(cls, value: list[MemoryId]) -> list[MemoryId]:
        """This validator enforces unique related-shellbrain references."""

        if len(value) != len(set(value)):
            raise ValueError("related_memory_ids must be unique")
        return value


class MemoryCreateBody(StrictBaseModel):
    """This model defines create-body fields for immutable shellbrain records."""

    text: str
    scope: Literal["repo", "global"]
    kind: MemoryKindValue
    rationale: str | None = None
    links: MemoryCreateLinks = Field(default_factory=MemoryCreateLinks)
    evidence_refs: list[EvidenceRefText] = Field(min_length=1)

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(
        cls, value: list[EvidenceRefText]
    ) -> list[EvidenceRefText]:
        """This validator enforces unique evidence references."""

        EvidenceRefs.required(value)
        return value


class MemoryCreateRequest(StrictBaseModel):
    """This model defines the canonical create request payload."""

    op: Literal["create"] = "create"
    repo_id: RepoId
    memory: MemoryCreateBody


class ArchiveStateUpdate(StrictBaseModel):
    """This model defines archive-state update payload fields."""

    type: Literal["archive_state"]
    archived: bool
    rationale: str | None = None


class UtilityVoteUpdate(StrictBaseModel):
    """This model defines utility-vote update payload fields."""

    type: Literal["utility_vote"]
    problem_id: MemoryId
    vote: float = Field(ge=-1.0, le=1.0)
    rationale: str | None = None
    evidence_refs: list[EvidenceRefText] = Field(default_factory=list)

    @field_validator("vote")
    @classmethod
    def _validate_vote_value(cls, value: float) -> float:
        """Validate utility votes through the memory-domain value object."""

        UtilityVoteValue(value)
        return value

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(
        cls, value: list[EvidenceRefText]
    ) -> list[EvidenceRefText]:
        """This validator enforces unique utility evidence references."""

        EvidenceRefs.optional(value)
        return value


class FactUpdateLinkUpdate(StrictBaseModel):
    """This model defines fact-update-link payload fields."""

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
        """This validator enforces unique fact-update evidence references."""

        EvidenceRefs.optional(value)
        return value


class AssociationLinkUpdate(StrictBaseModel):
    """This model defines association-link update payload fields."""

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
        """Validate confidence through the memory-domain value object."""

        if value is not None:
            ConfidenceValue(value)
        return value

    @field_validator("salience")
    @classmethod
    def _validate_salience_value(cls, value: float | None) -> float | None:
        """Validate salience through the memory-domain value object."""

        if value is not None:
            SalienceValue(value)
        return value

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(
        cls, value: list[EvidenceRefText]
    ) -> list[EvidenceRefText]:
        """This validator enforces unique association evidence references."""

        EvidenceRefs.required(value)
        return value


UpdatePayload = Annotated[
    ArchiveStateUpdate
    | UtilityVoteUpdate
    | FactUpdateLinkUpdate
    | AssociationLinkUpdate,
    Field(discriminator="type"),
]


class MemoryUpdateRequest(StrictBaseModel):
    """This model defines the canonical update request payload."""

    op: Literal["update"] = "update"
    repo_id: RepoId
    memory_id: MemoryId
    update: UpdatePayload


class BatchUtilityVoteItem(StrictBaseModel):
    """One utility-vote update entry inside a batch update request."""

    memory_id: MemoryId
    update: UtilityVoteUpdate


class MemoryBatchUpdateRequest(StrictBaseModel):
    """This model defines the canonical batch utility-update payload."""

    op: Literal["update"] = "update"
    repo_id: RepoId
    updates: list[BatchUtilityVoteItem] = Field(min_length=1)
