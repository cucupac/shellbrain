"""This module defines strict internal request contracts for create, read, and update operations."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.entities.ids import EvidenceRefText, MemoryId, RepoId


MemoryKindValue = Literal["problem", "solution", "failed_tactic", "fact", "preference", "change", "frontier"]
AssociationRelationValue = Literal["depends_on", "associated_with", "matures_into"]
ConceptReadFacetValue = Literal["claims", "relations", "groundings", "memory_links", "evidence"]


class StrictBaseModel(BaseModel):
    """This base model enforces strict schemas by rejecting unknown fields."""

    model_config = ConfigDict(extra="forbid")


class ReadConceptsExpandRequest(StrictBaseModel):
    """This model defines concept-context read expansion controls."""

    mode: Literal["auto", "none", "explicit"] = "auto"
    refs: list[str] = Field(default_factory=list, max_length=5)
    facets: list[ConceptReadFacetValue] = Field(default_factory=list, max_length=5)
    max_auto: int = Field(default=2, ge=1, le=5)

    @field_validator("refs")
    @classmethod
    def _validate_refs_unique(cls, value: list[str]) -> list[str]:
        """This validator enforces unique concept refs."""

        if any(not ref.strip() for ref in value):
            raise ValueError("concept refs must be non-empty")
        if len(value) != len(set(value)):
            raise ValueError("concept refs must be unique")
        return value

    @field_validator("facets")
    @classmethod
    def _validate_facets_unique(cls, value: list[ConceptReadFacetValue]) -> list[ConceptReadFacetValue]:
        """This validator enforces unique concept facets."""

        if len(value) != len(set(value)):
            raise ValueError("concept facets must be unique")
        return value

    @model_validator(mode="after")
    def _validate_explicit_refs(self) -> "ReadConceptsExpandRequest":
        """Require explicit concept refs when explicit mode is requested."""

        if self.mode == "explicit" and not self.refs:
            raise ValueError("expand.concepts.mode=explicit requires refs")
        return self


class ReadExpandRequest(StrictBaseModel):
    """This model defines expansion knobs for read requests."""

    semantic_hops: int | None = Field(default=None, ge=0, le=3)
    include_problem_links: bool | None = None
    include_fact_update_links: bool | None = None
    include_association_links: bool | None = None
    max_association_depth: int | None = Field(default=None, ge=1, le=4)
    min_association_strength: float | None = Field(default=None, ge=0.0, le=1.0)
    concepts: ReadConceptsExpandRequest = Field(default_factory=ReadConceptsExpandRequest)


class MemoryReadRequest(StrictBaseModel):
    """This model defines the canonical read request payload."""

    op: Literal["read"] = "read"
    repo_id: RepoId
    mode: Literal["ambient", "targeted"]
    query: str = Field(min_length=1)
    include_global: bool | None = None
    kinds: list[MemoryKindValue] | None = Field(default=None, min_length=1)
    limit: int | None = Field(default=None, ge=1, le=100)
    expand: ReadExpandRequest | None = None

    @field_validator("kinds")
    @classmethod
    def _validate_kinds_unique(
        cls,
        value: list[MemoryKindValue] | None,
    ) -> list[MemoryKindValue] | None:
        """This validator enforces unique kinds filters for read requests."""

        if value is None:
            return value
        if len(value) != len(set(value)):
            raise ValueError("kinds must be unique")
        return value


class MemoryRecallRequest(StrictBaseModel):
    """This model defines the canonical recall request payload."""

    op: Literal["recall"] = "recall"
    repo_id: RepoId
    query: str = Field(min_length=1)
    limit: int | None = Field(default=None, ge=1, le=100)


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
    def _validate_evidence_unique(cls, value: list[EvidenceRefText]) -> list[EvidenceRefText]:
        """This validator enforces unique evidence references."""

        if len(value) != len(set(value)):
            raise ValueError("evidence_refs must be unique")
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

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(cls, value: list[EvidenceRefText]) -> list[EvidenceRefText]:
        """This validator enforces unique utility evidence references."""

        if len(value) != len(set(value)):
            raise ValueError("evidence_refs must be unique")
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
    def _validate_evidence_unique(cls, value: list[EvidenceRefText]) -> list[EvidenceRefText]:
        """This validator enforces unique fact-update evidence references."""

        if len(value) != len(set(value)):
            raise ValueError("evidence_refs must be unique")
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

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_unique(cls, value: list[EvidenceRefText]) -> list[EvidenceRefText]:
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
