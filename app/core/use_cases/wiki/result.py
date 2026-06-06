"""Page models returned by Shellbrain Wiki use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.core.entities.wiki_summaries import WikiSummaryView


@dataclass(frozen=True)
class WikiStatus:
    """Lifecycle and provenance summary for one displayed record."""

    status: str
    confidence: float | None = None
    currentness: str | None = None
    temporal_reason: str | None = None
    evidence_count: int = 0


@dataclass(frozen=True)
class WikiConceptListItem:
    """One concept listed on the wiki home or search page."""

    id: str
    slug: str
    name: str
    kind: str
    status: str
    scope_note: str | None
    definition: str | None
    claim_count: int
    memory_count: int
    evidence_count: int
    popularity_score: int


@dataclass(frozen=True)
class WikiConceptGroup:
    """Concepts grouped by their concept kind."""

    kind: str
    concepts: tuple[WikiConceptListItem, ...]


@dataclass(frozen=True)
class WikiRepositoryItem:
    """One repository listed on the wiki index."""

    repo_id: str
    repo_root: str | None
    concept_count: int
    memory_count: int
    evidence_count: int
    last_seen_at: str | None
    is_current: bool
    popularity_score: int


@dataclass(frozen=True)
class WikiIndexResult:
    """Top-level Shellbrain Wiki repository index."""

    current_repo_id: str
    repositories: tuple[WikiRepositoryItem, ...]


@dataclass(frozen=True)
class WikiHomeResult:
    """One repository's Shellbrain Wiki home page data."""

    repo_id: str
    groups: tuple[WikiConceptGroup, ...]
    summary: WikiSummaryView | None = None


@dataclass(frozen=True)
class WikiClaimItem:
    """One concept claim displayed in the wiki."""

    id: str
    claim_type: str
    text: str
    status: WikiStatus


@dataclass(frozen=True)
class WikiConceptRef:
    """A typed reference to one concept."""

    id: str
    slug: str
    name: str
    kind: str


@dataclass(frozen=True)
class WikiRelationItem:
    """One typed concept-to-concept relation."""

    id: str
    predicate: str
    subject: WikiConceptRef
    object: WikiConceptRef
    status: WikiStatus


@dataclass(frozen=True)
class WikiMemoryLinkItem:
    """One concept-to-memory link."""

    id: str
    role: str
    memory_id: str
    memory_kind: str
    memory_text: str
    memory_status: str
    status: WikiStatus


@dataclass(frozen=True)
class WikiGroundingItem:
    """One concept grounding to a concrete anchor."""

    id: str
    role: str
    anchor_id: str
    anchor_kind: str
    locator: str
    anchor_status: str
    status: WikiStatus


@dataclass(frozen=True)
class WikiEvidenceItem:
    """One evidence link displayed in the wiki."""

    evidence_id: str
    target_type: str
    target_id: str
    role: str
    source_kind: str
    source_ref: str
    created_at: str | None


@dataclass(frozen=True)
class WikiConceptPageResult:
    """One concept wiki page."""

    id: str
    repo_id: str
    slug: str
    name: str
    kind: str
    status: str
    definition: str | None
    status_rollup: dict[str, int]
    evidence_total: int
    key_claims: tuple[WikiClaimItem, ...]
    summary: WikiSummaryView | None = None


@dataclass(frozen=True)
class WikiConceptFacetResult:
    """A progressively loaded concept facet."""

    concept: WikiConceptRef
    repo_id: str
    facet: str
    claims: tuple[WikiClaimItem, ...] = ()
    relations: tuple[WikiRelationItem, ...] = ()
    memory_links: tuple[WikiMemoryLinkItem, ...] = ()
    groundings: tuple[WikiGroundingItem, ...] = ()
    evidence: tuple[WikiEvidenceItem, ...] = ()


@dataclass(frozen=True)
class WikiMemoryConceptLink:
    """A concept linked to one memory."""

    concept: WikiConceptRef
    role: str
    status: WikiStatus


@dataclass(frozen=True)
class WikiMemoryNeighbor:
    """A memory related to another memory."""

    memory_id: str
    kind: str
    text: str
    status: str
    relation_type: str


@dataclass(frozen=True)
class WikiMemoryPageResult:
    """One atomic memory wiki page."""

    id: str
    repo_id: str
    kind: str
    text: str
    status: WikiStatus
    concept_links: tuple[WikiMemoryConceptLink, ...]
    neighbors: tuple[WikiMemoryNeighbor, ...]
    evidence: tuple[WikiEvidenceItem, ...]


@dataclass(frozen=True)
class WikiAnchorConceptLink:
    """A concept grounded in one anchor."""

    concept: WikiConceptRef
    grounding_id: str
    role: str
    status: WikiStatus


@dataclass(frozen=True)
class WikiAnchorPageResult:
    """One anchor wiki page."""

    id: str
    repo_id: str
    kind: str
    locator: str
    status: str
    concept_links: tuple[WikiAnchorConceptLink, ...]


@dataclass(frozen=True)
class WikiEvidenceTargetItem:
    """A target linked to one evidence source."""

    link_id: str
    target_type: str
    target_id: str
    role: str
    created_at: str | None


@dataclass(frozen=True)
class WikiEvidencePageResult:
    """One evidence source wiki page."""

    id: str
    repo_id: str
    source_kind: str
    source_ref: str
    created_at: str | None
    linked_targets: tuple[WikiEvidenceTargetItem, ...]


@dataclass(frozen=True)
class WikiSearchHit:
    """One wiki search result."""

    record_type: Literal["concept", "memory"]
    id: str
    title: str
    subtitle: str
    url: str


@dataclass(frozen=True)
class WikiSearchResult:
    """Keyword-only wiki search result."""

    repo_id: str
    query: str
    hits: tuple[WikiSearchHit, ...]


WikiRouteResult = (
    WikiIndexResult
    |
    WikiHomeResult
    | WikiConceptPageResult
    | WikiConceptFacetResult
    | WikiMemoryPageResult
    | WikiAnchorPageResult
    | WikiEvidencePageResult
    | WikiSearchResult
)


def locator_text(locator: dict[str, Any]) -> str:
    """Return a stable compact anchor locator string."""

    parts = [f"{key}={locator[key]}" for key in sorted(locator)]
    return ", ".join(parts) if parts else "{}"
