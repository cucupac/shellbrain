"""This module defines strict request contracts for retrieval operations."""

from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.core.contracts.base import StrictBaseModel
from app.core.contracts.memories import MemoryKindValue
from app.core.entities.ids import RepoId


ConceptReadFacetValue = Literal[
    "claims", "relations", "groundings", "memory_links", "evidence"
]


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
    def _validate_facets_unique(
        cls, value: list[ConceptReadFacetValue]
    ) -> list[ConceptReadFacetValue]:
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
    concepts: ReadConceptsExpandRequest = Field(
        default_factory=ReadConceptsExpandRequest
    )


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
