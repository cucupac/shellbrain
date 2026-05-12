"""Request types for the concept add use case."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ConceptKindValue = Literal[
    "domain", "capability", "process", "entity", "rule", "component"
]
ConceptStatusValue = Literal["active", "deprecated", "archived"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AddConceptAction(_StrictModel):
    """Create one concept container and aliases."""

    type: Literal["add_concept"]
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: ConceptKindValue
    status: ConceptStatusValue = "active"
    scope_note: str | None = None
    aliases: list[str] = Field(default_factory=list)


ConceptAddAction = AddConceptAction


class ConceptAddRequest(_StrictModel):
    """Canonical concept-add request."""

    schema_version: Literal["concept.v1"]
    repo_id: str
    actions: list[ConceptAddAction] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_unique_slugs(self) -> "ConceptAddRequest":
        slugs = [_normalize_slug(action.slug) for action in self.actions]
        if len(slugs) != len(set(slugs)):
            raise ValueError("concept add actions must use unique slugs")
        return self


def _normalize_slug(value: str) -> str:
    return "-".join(" ".join(value.strip().lower().split()).replace("_", "-").split())
