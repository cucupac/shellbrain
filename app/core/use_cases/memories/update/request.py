"""Request types for the memory update use case."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic import model_validator

from app.core.entities.ids import EvidenceRefText, MemoryId, RepoId
from app.core.entities.memories import (
    AssociationRelationValue,
    ConfidenceValue,
    EvidenceRefs,
    MemoryLifecycleActorValue,
    MemoryLifecycleStatusValue,
    SalienceValue,
    UtilityVoteValue,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


EvidenceSourceKindValue = Literal[
    "episode_event", "anchor", "memory", "commit", "transcript", "test", "manual"
]


_EVIDENCE_REF_FIELD_BY_KIND: dict[str, str] = {
    "episode_event": "ref",
    "anchor": "anchor_id",
    "memory": "memory_id",
    "commit": "commit_ref",
    "transcript": "transcript_ref",
    "test": "note",
    "manual": "note",
}
_EVIDENCE_REF_FIELDS = frozenset(
    (
        "ref",
        "episode_event_id",
        "anchor_id",
        "memory_id",
        "commit_ref",
        "transcript_ref",
        "note",
    )
)


def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return value
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


class MemoryLifecycleEvidencePayload(_StrictModel):
    """Evidence supplied inline with a concrete memory lifecycle update."""

    kind: EvidenceSourceKindValue
    ref: str | None = None
    episode_event_id: str | None = None
    anchor_id: str | None = None
    memory_id: str | None = None
    commit_ref: str | None = None
    transcript_ref: str | None = None
    note: str | None = None

    @field_validator(
        "ref",
        "episode_event_id",
        "anchor_id",
        "memory_id",
        "commit_ref",
        "transcript_ref",
        "note",
    )
    @classmethod
    def _validate_optional_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, field_name="lifecycle evidence reference")

    @model_validator(mode="after")
    def _validate_required_reference(self) -> "MemoryLifecycleEvidencePayload":
        if self.kind == "episode_event":
            event_refs = {
                value
                for value in (self.ref, self.episode_event_id)
                if value is not None
            }
            if not event_refs:
                raise ValueError("episode_event evidence requires ref")
            if len(event_refs) > 1:
                raise ValueError("episode_event ref and episode_event_id differ")
            extra_fields = {
                field
                for field in _EVIDENCE_REF_FIELDS - {"ref", "episode_event_id"}
                if getattr(self, field) is not None
            }
            if extra_fields:
                raise ValueError("episode_event evidence only accepts ref")
            self.ref = next(iter(event_refs))
            self.episode_event_id = self.ref
            return self

        required_field = _EVIDENCE_REF_FIELD_BY_KIND[self.kind]
        present_fields = {
            field
            for field in _EVIDENCE_REF_FIELDS
            if getattr(self, field) is not None
        }
        if required_field not in present_fields:
            raise ValueError(f"{self.kind} evidence requires {required_field}")
        extra_fields = present_fields - {required_field}
        if extra_fields:
            raise ValueError(f"{self.kind} evidence only accepts {required_field}")
        return self


class MemoryLifecycleUpdate(_StrictModel):
    """Lifecycle-state update payload fields."""

    type: Literal["update_lifecycle"]
    status: MemoryLifecycleStatusValue
    rationale: str = Field(min_length=1)
    actor: MemoryLifecycleActorValue
    validated_at: datetime | None = None
    superseded_by_id: MemoryId | None = None
    evidence: list[MemoryLifecycleEvidencePayload] = Field(min_length=1)

    @field_validator("rationale", "superseded_by_id")
    @classmethod
    def _validate_optional_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, field_name="lifecycle update field")

    @model_validator(mode="after")
    def _validate_supersession(self) -> "MemoryLifecycleUpdate":
        if self.status == "superseded" and self.superseded_by_id is None:
            raise ValueError("superseded lifecycle updates require superseded_by_id")
        if self.status != "superseded" and self.superseded_by_id is not None:
            raise ValueError(
                "superseded_by_id is only valid for superseded lifecycle updates"
            )
        return self


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
    confidence: float = Field(ge=0.0, le=1.0)
    salience: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None
    evidence_refs: list[EvidenceRefText] = Field(min_length=1)

    @field_validator("confidence")
    @classmethod
    def _validate_confidence_value(cls, value: float) -> float:
        ConfidenceValue(value)
        return value

    @field_validator("salience")
    @classmethod
    def _validate_salience_value(cls, value: float) -> float:
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
    MemoryLifecycleUpdate
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
