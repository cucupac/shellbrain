"""Request types for Shellbrain Wiki read-only pages."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ConceptFacetValue = Literal["claims", "relations", "memory-links", "groundings", "evidence"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _required_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


class WikiIndexRequest(_StrictModel):
    """Request for the Shellbrain Wiki repository index."""

    current_repo_id: str

    @field_validator("current_repo_id")
    @classmethod
    def _validate_current_repo_id(cls, value: str) -> str:
        return _required_text(value, field_name="current_repo_id")


class WikiRepoRequest(_StrictModel):
    """Request for one repository's Shellbrain Wiki home page."""

    repo_id: str
    now: datetime

    @field_validator("repo_id")
    @classmethod
    def _validate_repo_id(cls, value: str) -> str:
        return _required_text(value, field_name="repo_id")


class WikiConceptRequest(WikiRepoRequest):
    """Request for one concept wiki page."""

    concept_ref: str = Field(min_length=1)

    @field_validator("concept_ref")
    @classmethod
    def _validate_concept_ref(cls, value: str) -> str:
        return _required_text(value, field_name="concept_ref")


class WikiConceptFacetRequest(WikiConceptRequest):
    """Request for one progressively loaded concept facet."""

    facet: ConceptFacetValue


class WikiMemoryRequest(WikiRepoRequest):
    """Request for one memory wiki page."""

    memory_id: str = Field(min_length=1)
    include_global: bool

    @field_validator("memory_id")
    @classmethod
    def _validate_memory_id(cls, value: str) -> str:
        return _required_text(value, field_name="memory_id")


class WikiAnchorRequest(WikiRepoRequest):
    """Request for one anchor wiki page."""

    anchor_id: str = Field(min_length=1)

    @field_validator("anchor_id")
    @classmethod
    def _validate_anchor_id(cls, value: str) -> str:
        return _required_text(value, field_name="anchor_id")


class WikiEvidenceRequest(WikiRepoRequest):
    """Request for one evidence wiki page."""

    evidence_id: str = Field(min_length=1)

    @field_validator("evidence_id")
    @classmethod
    def _validate_evidence_id(cls, value: str) -> str:
        return _required_text(value, field_name="evidence_id")


class WikiSearchRequest(WikiRepoRequest):
    """Request for the wiki jump/search page."""

    query: str = ""
    include_global: bool
    limit: int = Field(default=10, ge=1, le=25)

    @field_validator("query")
    @classmethod
    def _validate_query(cls, value: str) -> str:
        return value.strip()
