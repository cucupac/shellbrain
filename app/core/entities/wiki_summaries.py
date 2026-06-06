"""Core entities for generated Shellbrain Wiki summaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class WikiSummaryTargetType(str, Enum):
    """Wiki targets that can have generated article prose."""

    REPO = "repo"
    CONCEPT = "concept"


class WikiSummaryLinkTargetType(str, Enum):
    """Wiki page targets that generated prose can link to deterministically."""

    CONCEPT = "concept"
    MEMORY = "memory"
    ANCHOR = "anchor"
    EVIDENCE = "evidence"


class WikiSummaryGenerationStatus(str, Enum):
    """Durable generation status for one cached wiki summary."""

    PENDING = "pending"
    OK = "ok"
    FAILED = "failed"


class WikiSummaryFreshness(str, Enum):
    """Read-time freshness state for a cached wiki summary."""

    MISSING = "missing"
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"
    PENDING = "pending"
    FAILED = "failed"


class WikiSummarySourceVelocity(str, Enum):
    """How quickly one summary target's source facts are changing."""

    HIGH = "high"
    NORMAL = "normal"
    QUIET = "quiet"


@dataclass(frozen=True, kw_only=True)
class WikiSummaryTarget:
    """One repository-scoped wiki summary target."""

    repo_id: str
    target_type: WikiSummaryTargetType
    target_id: str


@dataclass(frozen=True, kw_only=True)
class WikiSummaryInputSnapshot:
    """Deterministic source payload used to generate one summary."""

    target: WikiSummaryTarget
    input_hash: str
    source_refs: tuple[str, ...]
    source_payload: dict[str, Any]
    source_velocity: WikiSummarySourceVelocity
    popularity_score: int
    latest_source_at: datetime | None = None


@dataclass(frozen=True, kw_only=True)
class WikiSummaryRecord:
    """Cached generated prose for one wiki target."""

    target: WikiSummaryTarget
    body: str | None
    input_hash: str | None
    source_refs: tuple[str, ...]
    generation_status: WikiSummaryGenerationStatus
    generated_at: datetime | None
    model: str | None
    prompt_version: str | None
    last_error_code: str | None
    last_error_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, kw_only=True)
class WikiSummaryLinkTarget:
    """One deterministic wiki page target that may be linked from summary prose."""

    target_type: WikiSummaryLinkTargetType
    target_id: str
    label: str
    slug: str | None = None


@dataclass(frozen=True, kw_only=True)
class WikiSummaryView:
    """Summary state attached to a rendered wiki page model."""

    target: WikiSummaryTarget
    freshness: WikiSummaryFreshness
    body: str | None
    generated_at: datetime | None
    stale_reason: str | None
    generation_status: WikiSummaryGenerationStatus | None
    link_targets: tuple[WikiSummaryLinkTarget, ...] = ()
