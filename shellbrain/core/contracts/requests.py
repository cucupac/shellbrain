"""This module defines strict internal request contracts for create, read, and update operations."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictBaseModel(BaseModel):
    """This base model enforces strict schemas by rejecting unknown fields."""

    model_config = ConfigDict(extra="forbid")


class ReadExpandRequest(StrictBaseModel):
    """This model defines expansion knobs for read requests."""

    semantic_hops: int | None = Field(default=None, ge=0, le=3)
    include_problem_links: bool | None = None
    include_fact_update_links: bool | None = None
    include_association_links: bool | None = None
    max_association_depth: int | None = Field(default=None, ge=1, le=4)
    min_association_strength: float | None = Field(default=None, ge=0.0, le=1.0)


class MemoryReadRequest(StrictBaseModel):
    """This model defines the canonical read request payload."""

    op: Literal["read"] = "read"
    repo_id: str
    mode: Literal["ambient", "targeted"]
    query: str = Field(min_length=1)
    include_global: bool | None = None
    kinds: (
        list[Literal["problem", "solution", "failed_tactic", "fact", "preference", "change"]] | None
    ) = None
    limit: int | None = Field(default=None, ge=1, le=100)
    expand: ReadExpandRequest | None = None

    @field_validator("kinds")
    @classmethod
    def _validate_kinds_unique(
        cls,
        value: list[Literal["problem", "solution", "failed_tactic", "fact", "preference", "change"]] | None,
    ) -> list[Literal["problem", "solution", "failed_tactic", "fact", "preference", "change"]] | None:
        """This validator enforces unique kinds filters for read requests."""

        if value is None:
            return value
        if len(value) != len(set(value)):
            raise ValueError("kinds must be unique")
        return value


class EpisodeEventsRequest(StrictBaseModel):
    """This model defines the canonical episode-events request payload."""

    op: Literal["events"] = "events"
    repo_id: str
    limit: int = Field(default=20, ge=1, le=100)


class MemoryCreateAssociationLink(StrictBaseModel):
    """This model defines a typed explicit association link payload on create."""

    to_memory_id: str
    relation_type: Literal["depends_on", "associated_with"]
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    salience: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = None


class MemoryCreateLinks(StrictBaseModel):
    """This model defines optional link payloads on create requests."""

    problem_id: str | None = None
    related_memory_ids: list[str] = Field(default_factory=list)
    associations: list[MemoryCreateAssociationLink] = Field(default_factory=list)

    @field_validator("related_memory_ids")
    @classmethod
    def _validate_related_unique(cls, value: list[str]) -> list[str]:
        """This validator enforces unique related-shellbrain references."""

        if len(value) != len(set(value)):
            raise ValueError("related_memory_ids must be unique")
        return value


class MemoryCreateBody(StrictBaseModel):
    """This model defines create-body fields for immutable shellbrain records."""

    text: str
    scope: Literal["repo", "global"]
    kind: Literal["problem", "solution", "failed_tactic", "fact", "preference", "change"]
    rationale: str | None = None
    links: MemoryCreateLinks = Field(default_factory=MemoryCreateLinks)
    evidence_refs: list[str] = Field(min_length=1)

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(cls, value: list[str]) -> list[str]:
        """This validator enforces unique evidence references."""

        if len(value) != len(set(value)):
            raise ValueError("evidence_refs must be unique")
        return value


class MemoryCreateRequest(StrictBaseModel):
    """This model defines the canonical create request payload."""

    op: Literal["create"] = "create"
    repo_id: str
    memory: MemoryCreateBody


class ArchiveStateUpdate(StrictBaseModel):
    """This model defines archive-state update payload fields."""

    type: Literal["archive_state"]
    archived: bool
    rationale: str | None = None


class UtilityVoteUpdate(StrictBaseModel):
    """This model defines utility-vote update payload fields."""

    type: Literal["utility_vote"]
    problem_id: str
    vote: float = Field(ge=-1.0, le=1.0)
    rationale: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(cls, value: list[str]) -> list[str]:
        """This validator enforces unique utility evidence references."""

        if len(value) != len(set(value)):
            raise ValueError("evidence_refs must be unique")
        return value


class FactUpdateLinkUpdate(StrictBaseModel):
    """This model defines fact-update-link payload fields."""

    type: Literal["fact_update_link"]
    old_fact_id: str
    new_fact_id: str
    rationale: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(cls, value: list[str]) -> list[str]:
        """This validator enforces unique fact-update evidence references."""

        if len(value) != len(set(value)):
            raise ValueError("evidence_refs must be unique")
        return value


class AssociationLinkUpdate(StrictBaseModel):
    """This model defines association-link update payload fields."""

    type: Literal["association_link"]
    to_memory_id: str
    relation_type: Literal["depends_on", "associated_with"]
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    salience: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = None
    evidence_refs: list[str] = Field(min_length=1)

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(cls, value: list[str]) -> list[str]:
        """This validator enforces unique association evidence references."""

        if len(value) != len(set(value)):
            raise ValueError("evidence_refs must be unique")
        return value


UpdatePayload = Annotated[
    ArchiveStateUpdate | UtilityVoteUpdate | FactUpdateLinkUpdate | AssociationLinkUpdate,
    Field(discriminator="type"),
]


class MemoryUpdateRequest(StrictBaseModel):
    """This model defines the canonical update request payload."""

    op: Literal["update"] = "update"
    repo_id: str
    memory_id: str
    update: UpdatePayload
