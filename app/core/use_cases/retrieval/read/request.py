"""Request types for the memory read use case."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.entities.ids import RepoId
from app.core.entities.memories import MemoryKindValue


ConceptReadFacetValue = Literal[
    "claims", "relations", "groundings", "memory_links", "evidence"
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadConceptsExpandRequest(_StrictModel):
    """Concept-context expansion controls for read requests."""

    mode: Literal["auto", "none", "explicit"] = "auto"
    refs: list[str] = Field(default_factory=list, max_length=5)
    facets: list[ConceptReadFacetValue] = Field(default_factory=list, max_length=5)
    max_auto: int = Field(default=2, ge=1, le=5)

    @field_validator("refs")
    @classmethod
    def _validate_refs_unique(cls, value: list[str]) -> list[str]:
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
        if len(value) != len(set(value)):
            raise ValueError("concept facets must be unique")
        return value

    @model_validator(mode="after")
    def _validate_explicit_refs(self) -> "ReadConceptsExpandRequest":
        if self.mode == "explicit" and not self.refs:
            raise ValueError("expand.concepts.mode=explicit requires refs")
        return self


class ReadExpandRequest(_StrictModel):
    """Expansion knobs for read requests."""

    semantic_hops: int | None = Field(default=None, ge=0, le=3)
    include_problem_links: bool | None = None
    include_fact_update_links: bool | None = None
    include_association_links: bool | None = None
    max_association_depth: int | None = Field(default=None, ge=1, le=4)
    min_association_strength: float | None = Field(default=None, ge=0.0, le=1.0)
    concepts: ReadConceptsExpandRequest = Field(
        default_factory=ReadConceptsExpandRequest
    )


class MemoryReadRequest(_StrictModel):
    """Canonical read request payload."""

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
        if value is None:
            return value
        if len(value) != len(set(value)):
            raise ValueError("kinds must be unique")
        return value
