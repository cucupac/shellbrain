"""Strict request contracts for the concept-context graph endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from app.core.contracts.base import StrictBaseModel


ConceptKindValue = Literal[
    "domain", "capability", "process", "entity", "rule", "component"
]
ConceptStatusValue = Literal["active", "deprecated", "archived"]
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
    "memory",
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
    "changed",
    "validated",
    "contradicted",
    "warned_about",
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
ConceptShowIncludeValue = Literal[
    "claims", "relations", "groundings", "memory_links", "preview_concept"
]


class ConceptEvidencePayload(StrictBaseModel):
    """Evidence supplied inline with one truth-bearing concept action."""

    kind: ConceptEvidenceKindValue
    anchor_id: str | None = None
    memory_id: str | None = None
    commit_ref: str | None = None
    transcript_ref: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _validate_required_reference(self) -> "ConceptEvidencePayload":
        """Require the reference field implied by the evidence kind."""

        if self.kind == "anchor" and not self.anchor_id:
            raise ValueError("anchor evidence requires anchor_id")
        if self.kind == "memory" and not self.memory_id:
            raise ValueError("memory evidence requires memory_id")
        if self.kind == "commit" and not self.commit_ref:
            raise ValueError("commit evidence requires commit_ref")
        if self.kind == "transcript" and not self.transcript_ref:
            raise ValueError("transcript evidence requires transcript_ref")
        if self.kind in {"manual", "test"} and not self.note:
            raise ValueError(f"{self.kind} evidence requires note")
        return self


class ConceptLifecycleActionFields(StrictBaseModel):
    """Shared optional lifecycle fields on concept write actions."""

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    observed_at: datetime | None = None
    validated_at: datetime | None = None
    source_kind: ConceptSourceKindValue | None = None
    source_ref: str | None = None
    created_by: ConceptCreatedByValue = "manual"


class AddConceptAction(StrictBaseModel):
    """Create one concept container and aliases."""

    type: Literal["add_concept"]
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: ConceptKindValue
    status: ConceptStatusValue = "active"
    scope_note: str | None = None
    aliases: list[str] = Field(default_factory=list)


class UpdateConceptAction(StrictBaseModel):
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
        """Require at least one mutable field."""

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


class EnsureAnchorAction(StrictBaseModel):
    """Create or fetch a real-world anchor by canonical locator."""

    type: Literal["ensure_anchor"]
    kind: AnchorKindValue
    locator: dict[str, Any] = Field(default_factory=dict)


class AnchorSelector(StrictBaseModel):
    """Reference an existing anchor or define an inline anchor to upsert."""

    id: str | None = None
    kind: AnchorKindValue | None = None
    locator: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_selector(self) -> "AnchorSelector":
        """Require either an id or a complete inline anchor."""

        has_inline = self.kind is not None and self.locator is not None
        if not self.id and not has_inline:
            raise ValueError("anchor requires id or kind+locator")
        if self.id and (self.kind is not None or self.locator is not None):
            raise ValueError("anchor selector cannot mix id with kind/locator")
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


ConceptAddAction = AddConceptAction


ConceptUpdateAction = Annotated[
    UpdateConceptAction
    | AddRelationAction
    | AddClaimAction
    | EnsureAnchorAction
    | AddGroundingAction
    | LinkMemoryAction,
    Field(discriminator="type"),
]


class ConceptAddRequest(StrictBaseModel):
    """Canonical concept-add request."""

    schema_version: Literal["concept.v1"]
    repo_id: str
    actions: list[ConceptAddAction] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_unique_slugs(self) -> "ConceptAddRequest":
        """Reject duplicate concept slugs within one add batch."""

        slugs = [_normalize_slug(action.slug) for action in self.actions]
        if len(slugs) != len(set(slugs)):
            raise ValueError("concept add actions must use unique slugs")
        return self


class ConceptUpdateRequest(StrictBaseModel):
    """Canonical concept-update request."""

    schema_version: Literal["concept.v1"]
    repo_id: str
    actions: list[ConceptUpdateAction] = Field(min_length=1)


class ConceptShowRequest(StrictBaseModel):
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
        """Reject duplicate show facets."""

        if len(value) != len(set(value)):
            raise ValueError("concept show include facets must be unique")
        return value


def _normalize_slug(value: str) -> str:
    return "-".join(" ".join(value.strip().lower().split()).replace("_", "-").split())
