"""Request types for the concept add use case."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ConceptKindValue = Literal[
    "domain", "capability", "process", "entity", "rule", "component"
]
ConceptStatusValue = Literal["active", "deprecated", "archived"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _normalize_required_string(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


class AddConceptAction(_StrictModel):
    """Create one concept container and aliases."""

    type: Literal["add_concept"]
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: ConceptKindValue
    status: ConceptStatusValue = "active"
    scope_note: str | None = None
    aliases: list[str] = Field(default_factory=list)

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, value: str) -> str:
        return _normalize_required_string(value, field_name="slug")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _normalize_required_string(value, field_name="name")

    @field_validator("aliases")
    @classmethod
    def _validate_aliases(cls, value: list[str]) -> list[str]:
        normalized = [
            _normalize_required_string(alias, field_name="aliases")
            for alias in value
        ]
        if len(normalized) != len(set(normalized)):
            raise ValueError("aliases must be unique")
        return normalized


ConceptAddAction = AddConceptAction


class ConceptAddRequest(_StrictModel):
    """Canonical concept-add request."""

    schema_version: Literal["concept.v1"]
    repo_id: str
    actions: list[ConceptAddAction] = Field(min_length=1)

    @field_validator("repo_id")
    @classmethod
    def _validate_repo_id(cls, value: str) -> str:
        return _normalize_required_string(value, field_name="repo_id")

    @model_validator(mode="after")
    def _validate_unique_slugs(self) -> "ConceptAddRequest":
        slugs = [_normalize_slug(action.slug) for action in self.actions]
        if len(slugs) != len(set(slugs)):
            raise ValueError("concept add actions must use unique slugs")
        return self


def _normalize_slug(value: str) -> str:
    return "-".join(" ".join(value.strip().lower().split()).replace("_", "-").split())
