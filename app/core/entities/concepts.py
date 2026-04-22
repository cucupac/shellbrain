"""Core entities and enums for the typed concept-context graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ConceptKind(str, Enum):
    """Allowed high-level concept kinds."""

    DOMAIN = "domain"
    CAPABILITY = "capability"
    PROCESS = "process"
    ENTITY = "entity"
    RULE = "rule"
    COMPONENT = "component"


class ConceptStatus(str, Enum):
    """Lifecycle state for concept containers."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ConceptLifecycleStatus(str, Enum):
    """Lifecycle state for truth-bearing concept records."""

    ACTIVE = "active"
    MAYBE_STALE = "maybe_stale"
    STALE = "stale"
    SUPERSEDED = "superseded"
    WRONG = "wrong"


class ConceptRelationPredicate(str, Enum):
    """Allowed concept-to-concept predicates."""

    CONTAINS = "contains"
    INVOLVES = "involves"
    PRECEDES = "precedes"
    CONSTRAINS = "constrains"
    DEPENDS_ON = "depends_on"


class ConceptClaimType(str, Enum):
    """Allowed concept claim types."""

    DEFINITION = "definition"
    BEHAVIOR = "behavior"
    INVARIANT = "invariant"
    FAILURE_MODE = "failure_mode"
    USAGE_NOTE = "usage_note"
    OPEN_QUESTION = "open_question"


class AnchorKind(str, Enum):
    """Allowed real-world locator kinds."""

    FILE = "file"
    SYMBOL = "symbol"
    LINE_RANGE = "line_range"
    API_ROUTE = "api_route"
    DB_TABLE = "db_table"
    SCHEMA = "schema"
    CONFIG_KEY = "config_key"
    TEST = "test"
    METRIC = "metric"
    LOG = "log"
    DOC = "doc"
    COMMIT = "commit"
    MEMORY = "memory"


class AnchorStatus(str, Enum):
    """Lifecycle state for real-world locators."""

    ACTIVE = "active"
    MAYBE_STALE = "maybe_stale"
    STALE = "stale"
    DEPRECATED = "deprecated"


class ConceptGroundingRole(str, Enum):
    """Allowed concept-to-anchor grounding roles."""

    IMPLEMENTATION = "implementation"
    ENTRYPOINT = "entrypoint"
    STORAGE = "storage"
    CONFIGURATION = "configuration"
    TEST = "test"
    OBSERVABILITY = "observability"
    DOCUMENTATION = "documentation"


class ConceptMemoryLinkRole(str, Enum):
    """Allowed concept-to-memory link roles."""

    EXAMPLE_OF = "example_of"
    SOLUTION_FOR = "solution_for"
    FAILED_TACTIC_FOR = "failed_tactic_for"
    CHANGED = "changed"
    VALIDATED = "validated"
    CONTRADICTED = "contradicted"
    WARNED_ABOUT = "warned_about"


class ConceptEvidenceTargetType(str, Enum):
    """Truth-bearing concept record types that evidence may target."""

    RELATION = "relation"
    CLAIM = "claim"
    GROUNDING = "grounding"
    MEMORY_LINK = "memory_link"


class ConceptEvidenceKind(str, Enum):
    """Allowed evidence source kinds for concept records."""

    ANCHOR = "anchor"
    MEMORY = "memory"
    COMMIT = "commit"
    TRANSCRIPT = "transcript"
    TEST = "test"
    MANUAL = "manual"


class ConceptSourceKind(str, Enum):
    """Allowed source refs on concept lifecycle records."""

    COMMIT = "commit"
    FILE_HASH = "file_hash"
    SYMBOL_HASH = "symbol_hash"
    MEMORY = "memory"
    TRANSCRIPT_EVENT = "transcript_event"
    MANUAL = "manual"
    DOC = "doc"
    RUNTIME_TRACE = "runtime_trace"


class ConceptCreatedBy(str, Enum):
    """Allowed authorship channels for concept records."""

    WORKER = "worker"
    LIBRARIAN = "librarian"
    MANUAL = "manual"
    IMPORT = "import"


class GraphPatchStatus(str, Enum):
    """Allowed graph patch lifecycle states."""

    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"


@dataclass(frozen=True, kw_only=True)
class Concept:
    """One durable concept container."""

    id: str
    repo_id: str
    slug: str
    name: str
    kind: ConceptKind
    status: ConceptStatus = ConceptStatus.ACTIVE
    scope_note: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class ConceptAlias:
    """One alternate label for a concept."""

    concept_id: str
    repo_id: str
    alias: str
    normalized_alias: str
    created_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class ConceptLifecycle:
    """Shared lifecycle fields for truth-bearing concept records."""

    status: ConceptLifecycleStatus = ConceptLifecycleStatus.ACTIVE
    confidence: float = 0.5
    observed_at: datetime | None = None
    validated_at: datetime | None = None
    source_kind: ConceptSourceKind | None = None
    source_ref: str | None = None
    superseded_by_id: str | None = None
    created_by: ConceptCreatedBy = ConceptCreatedBy.MANUAL


@dataclass(frozen=True, kw_only=True)
class ConceptRelation:
    """One typed concept-to-concept relation."""

    id: str
    repo_id: str
    subject_concept_id: str
    predicate: ConceptRelationPredicate
    object_concept_id: str
    lifecycle: ConceptLifecycle = field(default_factory=ConceptLifecycle)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class ConceptClaim:
    """One typed statement Shellbrain believes about a concept."""

    id: str
    repo_id: str
    concept_id: str
    claim_type: ConceptClaimType
    text: str
    normalized_text: str
    lifecycle: ConceptLifecycle = field(default_factory=ConceptLifecycle)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class Anchor:
    """One real-world locator that grounds a concept."""

    id: str
    repo_id: str
    kind: AnchorKind
    locator_json: dict[str, Any]
    canonical_locator_hash: str
    status: AnchorStatus = AnchorStatus.ACTIVE
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class ConceptGrounding:
    """One typed link from concept space to a real-world anchor."""

    id: str
    repo_id: str
    concept_id: str
    role: ConceptGroundingRole
    anchor_id: str
    lifecycle: ConceptLifecycle = field(default_factory=ConceptLifecycle)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class ConceptMemoryLink:
    """One typed link from an existing Shellbrain memory to a concept."""

    id: str
    repo_id: str
    concept_id: str
    role: ConceptMemoryLinkRole
    memory_id: str
    lifecycle: ConceptLifecycle = field(default_factory=ConceptLifecycle)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class ConceptEvidence:
    """One evidence pointer attached to a truth-bearing concept record."""

    id: str
    repo_id: str
    target_type: ConceptEvidenceTargetType
    target_id: str
    evidence_kind: ConceptEvidenceKind
    anchor_id: str | None = None
    memory_id: str | None = None
    commit_ref: str | None = None
    transcript_ref: str | None = None
    note: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class GraphPatch:
    """Minimal reserved future graph-patch proposal record."""

    id: str
    repo_id: str
    schema_version: str
    status: GraphPatchStatus
    proposed_by: ConceptCreatedBy
    operations_json: list[dict[str, Any]]
    evidence_summary: str | None = None
    created_at: datetime | None = None
    applied_at: datetime | None = None
