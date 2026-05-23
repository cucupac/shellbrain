"""Request types for the concept update use case."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.use_cases.concepts.add.request import (
    ConceptKindValue,
    ConceptStatusValue,
)


ConceptRelationPredicateValue = Literal[
    "contains", "involves", "precedes", "constrains", "depends_on"
]
ConceptClaimTypeValue = Literal[
    "definition", "behavior", "invariant", "failure_mode", "usage_note", "open_question"
]
AnchorKindValue = Literal[
    "file",
    "symbol",
    "line_range",
    "api_route",
    "db_table",
    "schema",
    "config_key",
    "test",
    "metric",
    "log",
    "doc",
    "commit",
]
ConceptGroundingRoleValue = Literal[
    "implementation",
    "entrypoint",
    "storage",
    "configuration",
    "test",
    "observability",
    "documentation",
]
ConceptMemoryLinkRoleValue = Literal[
    "example_of",
    "solution_for",
    "failed_tactic_for",
    "warns_about",
    "change_relevant_to",
]
ConceptLifecycleTargetTypeValue = Literal[
    "relation", "claim", "grounding", "memory_link"
]
ConceptLifecycleStatusValue = Literal[
    "active", "maybe_stale", "stale", "superseded", "wrong", "archived"
]
ConceptEvidenceKindValue = Literal[
    "anchor", "memory", "commit", "transcript", "test", "manual"
]
ConceptSourceKindValue = Literal[
    "commit",
    "file_hash",
    "symbol_hash",
    "memory",
    "transcript_event",
    "manual",
    "doc",
    "runtime_trace",
]
ConceptCreatedByValue = Literal["worker", "librarian", "manual", "import"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


_EVIDENCE_REF_FIELD_BY_KIND: dict[str, str] = {
    "anchor": "anchor_id",
    "memory": "memory_id",
    "commit": "commit_ref",
    "transcript": "transcript_ref",
    "manual": "note",
    "test": "note",
}
_EVIDENCE_REF_FIELDS = frozenset(_EVIDENCE_REF_FIELD_BY_KIND.values())
_REQUIRED_LOCATOR_FIELDS: dict[str, tuple[str, ...]] = {
    "file": ("path",),
    "symbol": ("path", "symbol"),
    "line_range": ("path", "start_line", "end_line"),
    "api_route": ("path",),
    "db_table": ("name",),
    "schema": ("name",),
    "config_key": ("key",),
    "test": ("path",),
    "metric": ("name",),
    "log": ("path",),
    "doc": ("path",),
    "commit": ("ref",),
}


def _normalize_optional_text(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return value
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must be non-empty")
    return text


def _validate_locator_shape(kind: str, locator: dict[str, Any]) -> None:
    if not locator:
        raise ValueError("anchor locator must not be empty")
    required_fields = _REQUIRED_LOCATOR_FIELDS[kind]
    missing = [field for field in required_fields if field not in locator]
    if missing:
        raise ValueError(
            f"{kind} anchor locator requires: {', '.join(required_fields)}"
        )
    for key, value in locator.items():
        if not key.strip():
            raise ValueError("anchor locator keys must be non-empty")
        _validate_locator_value(kind=kind, key=key, value=value)
    if kind == "line_range":
        start_line = locator["start_line"]
        end_line = locator["end_line"]
        if end_line < start_line:
            raise ValueError("line_range locator end_line must be >= start_line")


def _validate_locator_value(*, kind: str, key: str, value: Any) -> None:
    if value is None:
        raise ValueError(f"{kind} anchor locator field {key!r} must not be null")
    if key in {"start_line", "end_line"}:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(
                f"{kind} anchor locator field {key!r} must be a positive integer"
            )
        return
    if isinstance(value, str):
        if not value.strip():
            raise ValueError(
                f"{kind} anchor locator field {key!r} must be non-empty"
            )
        return
    if isinstance(value, bool) or isinstance(value, (dict, list, tuple, set)):
        raise ValueError(
            f"{kind} anchor locator field {key!r} must be a non-empty scalar"
        )


class ConceptEvidencePayload(_StrictModel):
    """Evidence supplied inline with one truth-bearing concept action."""

    kind: ConceptEvidenceKindValue
    anchor_id: str | None = None
    memory_id: str | None = None
    commit_ref: str | None = None
    transcript_ref: str | None = None
    note: str | None = None

    @field_validator("anchor_id", "memory_id", "commit_ref", "transcript_ref", "note")
    @classmethod
    def _validate_optional_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, field_name="concept evidence reference")

    @model_validator(mode="after")
    def _validate_required_reference(self) -> "ConceptEvidencePayload":
        required_field = _EVIDENCE_REF_FIELD_BY_KIND[self.kind]
        present_fields = {
            field for field in _EVIDENCE_REF_FIELDS if getattr(self, field) is not None
        }
        if required_field not in present_fields:
            raise ValueError(f"{self.kind} evidence requires {required_field}")
        extra_fields = present_fields - {required_field}
        if extra_fields:
            raise ValueError(
                f"{self.kind} evidence only accepts {required_field}"
            )
        return self


class ConceptLifecycleActionFields(_StrictModel):
    """Shared optional lifecycle fields on concept write actions."""

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    observed_at: datetime | None = None
    validated_at: datetime | None = None
    source_kind: ConceptSourceKindValue | None = None
    source_ref: str | None = None
    created_by: ConceptCreatedByValue = "manual"


class UpdateConceptAction(_StrictModel):
    """Update one existing concept container and add aliases."""

    type: Literal["update_concept"]
    concept: str = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1)
    kind: ConceptKindValue | None = None
    status: ConceptStatusValue | None = None
    scope_note: str | None = None
    aliases: list[str] | None = None

    @model_validator(mode="after")
    def _validate_has_update(self) -> "UpdateConceptAction":
        if not (
            self.model_fields_set & {"name", "kind", "status", "scope_note", "aliases"}
        ):
            raise ValueError("update_concept requires at least one field to update")
        return self


class AddRelationAction(ConceptLifecycleActionFields):
    """Create an evidence-backed concept relation."""

    type: Literal["add_relation"]
    subject: str = Field(min_length=1)
    predicate: ConceptRelationPredicateValue
    object: str = Field(min_length=1)
    evidence: list[ConceptEvidencePayload] = Field(min_length=1)


class AddClaimAction(ConceptLifecycleActionFields):
    """Create an evidence-backed concept claim."""

    type: Literal["add_claim"]
    concept: str = Field(min_length=1)
    claim_type: ConceptClaimTypeValue
    text: str = Field(min_length=1)
    evidence: list[ConceptEvidencePayload] = Field(min_length=1)


class EnsureAnchorAction(_StrictModel):
    """Create or fetch a real-world anchor by canonical locator."""

    type: Literal["ensure_anchor"]
    kind: AnchorKindValue
    locator: dict[str, Any]

    @model_validator(mode="after")
    def _validate_locator(self) -> "EnsureAnchorAction":
        _validate_locator_shape(self.kind, self.locator)
        return self


class AnchorSelector(_StrictModel):
    """Reference an existing anchor or define an inline anchor to upsert."""

    id: str | None = None
    kind: AnchorKindValue | None = None
    locator: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_selector(self) -> "AnchorSelector":
        has_inline = self.kind is not None and self.locator is not None
        if not self.id and not has_inline:
            raise ValueError("anchor requires id or kind+locator")
        if self.id and (self.kind is not None or self.locator is not None):
            raise ValueError("anchor selector cannot mix id with kind/locator")
        if self.id is not None:
            self.id = _normalize_optional_text(self.id, field_name="anchor id")
        if has_inline:
            assert self.kind is not None and self.locator is not None
            _validate_locator_shape(self.kind, self.locator)
        return self


class AddGroundingAction(ConceptLifecycleActionFields):
    """Create an evidence-backed concept grounding."""

    type: Literal["add_grounding"]
    concept: str = Field(min_length=1)
    role: ConceptGroundingRoleValue
    anchor: AnchorSelector
    evidence: list[ConceptEvidencePayload] = Field(min_length=1)


class LinkMemoryAction(ConceptLifecycleActionFields):
    """Create an evidence-backed concept-memory link."""

    type: Literal["link_memory"]
    concept: str = Field(min_length=1)
    role: ConceptMemoryLinkRoleValue
    memory_id: str = Field(min_length=1)
    evidence: list[ConceptEvidencePayload] = Field(min_length=1)


class UpdateLifecycleAction(_StrictModel):
    """Change lifecycle state for an existing truth-bearing concept record."""

    type: Literal["update_lifecycle"]
    target_type: ConceptLifecycleTargetTypeValue
    target_id: str = Field(min_length=1)
    status: ConceptLifecycleStatusValue
    rationale: str = Field(min_length=1)
    actor: ConceptCreatedByValue
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    validated_at: datetime | None = None
    superseded_by_id: str | None = None
    evidence: list[ConceptEvidencePayload] = Field(min_length=1)

    @field_validator("target_id", "rationale", "superseded_by_id")
    @classmethod
    def _validate_optional_text(cls, value: str | None) -> str | None:
        return _normalize_optional_text(value, field_name="lifecycle update field")

    @model_validator(mode="after")
    def _validate_supersession(self) -> "UpdateLifecycleAction":
        if self.status == "superseded" and self.superseded_by_id is None:
            raise ValueError("superseded lifecycle updates require superseded_by_id")
        if self.status != "superseded" and self.superseded_by_id is not None:
            raise ValueError(
                "superseded_by_id is only valid for superseded lifecycle updates"
            )
        return self


ConceptUpdateAction = Annotated[
    UpdateConceptAction
    | AddRelationAction
    | AddClaimAction
    | EnsureAnchorAction
    | AddGroundingAction
    | LinkMemoryAction
    | UpdateLifecycleAction,
    Field(discriminator="type"),
]


class ConceptUpdateRequest(_StrictModel):
    """Canonical concept-update request."""

    schema_version: Literal["concept.v1"]
    repo_id: str
    actions: list[ConceptUpdateAction] = Field(min_length=1)
