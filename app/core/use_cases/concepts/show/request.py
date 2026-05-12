"""Request types for the concept show use case."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ConceptShowIncludeValue = Literal[
    "claims", "relations", "groundings", "memory_links", "preview_concept"
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConceptShowRequest(_StrictModel):
    """Canonical concept-show request."""

    schema_version: Literal["concept.v1"]
    repo_id: str
    concept: str = Field(min_length=1)
    include: list[ConceptShowIncludeValue] = Field(default_factory=list)

    @field_validator("include")
    @classmethod
    def _validate_include_unique(
        cls, value: list[ConceptShowIncludeValue]
    ) -> list[ConceptShowIncludeValue]:
        if len(value) != len(set(value)):
            raise ValueError("concept show include facets must be unique")
        return value
