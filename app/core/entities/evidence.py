"""This module defines evidence references and unified evidence-link entities."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.core.entities.ids import (
    AssociationEdgeId,
    EvidenceId,
    EvidenceRefText,
    MemoryId,
    RepoId,
)


class EvidenceTargetType(str, Enum):
    """Storage-neutral targets that may carry evidence."""

    MEMORY = "memory"
    FACT_UPDATE = "fact_update"
    ASSOCIATION_EDGE = "association_edge"
    UTILITY_OBSERVATION = "utility_observation"
    CONCEPT_CLAIM = "concept_claim"
    CONCEPT_RELATION = "concept_relation"
    CONCEPT_GROUNDING = "concept_grounding"
    CONCEPT_MEMORY_LINK = "concept_memory_link"
    CONCEPT_LIFECYCLE_EVENT = "concept_lifecycle_event"
    MEMORY_LIFECYCLE_EVENT = "memory_lifecycle_event"


class EvidenceSourceKind(str, Enum):
    """Storage-neutral kinds of evidence sources."""

    EPISODE_EVENT = "episode_event"
    ANCHOR = "anchor"
    MEMORY = "memory"
    COMMIT = "commit"
    TRANSCRIPT = "transcript"
    TEST = "test"
    MANUAL = "manual"


class EvidenceRole(str, Enum):
    """Semantic role an evidence source plays for a target."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    OBSERVED_IN = "observed_in"
    CREATED_FROM = "created_from"
    VALIDATED_BY = "validated_by"
    INVALIDATED_BY = "invalidated_by"
    EXPLAINS = "explains"


@dataclass(kw_only=True)
class EvidenceRef:
    """This dataclass models a canonical evidence reference entry."""

    id: EvidenceId
    repo_id: RepoId
    ref: EvidenceRefText
    kind: EvidenceSourceKind = EvidenceSourceKind.EPISODE_EVENT
    canonical_hash: str | None = None
    episode_event_id: str | None = None
    anchor_id: str | None = None
    memory_id: str | None = None
    commit_ref: str | None = None
    transcript_ref: str | None = None
    note: str | None = None


@dataclass(frozen=True, kw_only=True)
class EvidenceTarget:
    """One evidence-backed target in the unified evidence API."""

    target_type: EvidenceTargetType
    target_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "target_type", EvidenceTargetType(self.target_type)
        )
        if not self.target_id.strip():
            raise ValueError("evidence target_id must be non-empty")


@dataclass(frozen=True, kw_only=True)
class EvidenceSource:
    """One normalized source that can support an evidence-backed target."""

    source_kind: EvidenceSourceKind
    ref: str | None = None
    episode_event_id: str | None = None
    anchor_id: str | None = None
    memory_id: str | None = None
    commit_ref: str | None = None
    transcript_ref: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_kind", EvidenceSourceKind(self.source_kind)
        )
        if self.source_kind is EvidenceSourceKind.EPISODE_EVENT:
            event_ref = self.ref or self.episode_event_id
            if event_ref is None or not event_ref.strip():
                raise ValueError("episode_event evidence requires ref")
            if self.ref is not None and self.episode_event_id is not None:
                if self.ref != self.episode_event_id:
                    raise ValueError("episode_event ref and episode_event_id differ")
            object.__setattr__(self, "ref", event_ref)
            object.__setattr__(self, "episode_event_id", event_ref)
            _require_no_fields(
                self,
                "anchor_id",
                "memory_id",
                "commit_ref",
                "transcript_ref",
                "note",
            )
            return

        required_field = _SOURCE_REQUIRED_FIELD[self.source_kind]
        _require_one_field(self, required_field)
        _require_no_fields(
            self,
            *(
                field
                for field in _SOURCE_REFERENCE_FIELDS
                if field != required_field
            ),
            "ref",
            "episode_event_id",
        )


@dataclass(frozen=True, kw_only=True)
class EvidenceLinkView:
    """One resolved evidence link with a storage-neutral target and source."""

    target: EvidenceTarget
    source: EvidenceSource
    role: EvidenceRole
    evidence_id: EvidenceId | None = None
    created_at: datetime | None = None


@dataclass(kw_only=True)
class MemoryEvidenceLink:
    """This dataclass models a many-to-many link between shellbrain and evidence."""

    memory_id: MemoryId
    evidence_id: EvidenceId


@dataclass(kw_only=True)
class AssociationEdgeEvidenceLink:
    """This dataclass models a many-to-many link between association edges and evidence."""

    edge_id: AssociationEdgeId
    evidence_id: EvidenceId


_SOURCE_REQUIRED_FIELD: dict[EvidenceSourceKind, str] = {
    EvidenceSourceKind.ANCHOR: "anchor_id",
    EvidenceSourceKind.MEMORY: "memory_id",
    EvidenceSourceKind.COMMIT: "commit_ref",
    EvidenceSourceKind.TRANSCRIPT: "transcript_ref",
    EvidenceSourceKind.TEST: "note",
    EvidenceSourceKind.MANUAL: "note",
}
_SOURCE_REFERENCE_FIELDS = frozenset(_SOURCE_REQUIRED_FIELD.values())


def _require_one_field(source: EvidenceSource, field: str) -> None:
    value = getattr(source, field)
    if value is None or not str(value).strip():
        raise ValueError(f"{source.source_kind.value} evidence requires {field}")


def _require_no_fields(source: EvidenceSource, *fields: str) -> None:
    extra_fields = [
        field
        for field in fields
        if getattr(source, field) is not None
    ]
    if extra_fields:
        raise ValueError(
            f"{source.source_kind.value} evidence does not accept: "
            + ", ".join(sorted(extra_fields))
        )


def canonical_evidence_hash(source: EvidenceSource) -> str:
    """Return the source-only canonical hash used to dedupe evidence refs."""

    payload = {
        "kind": source.source_kind.value,
        "identity": _source_identity(source),
    }
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def evidence_source_ref(source: EvidenceSource) -> str:
    """Return the required display/source reference string for one evidence source."""

    return _source_identity(source)


def _source_identity(source: EvidenceSource) -> str:
    if source.source_kind is EvidenceSourceKind.EPISODE_EVENT:
        assert source.episode_event_id is not None
        return source.episode_event_id
    required_field = _SOURCE_REQUIRED_FIELD[source.source_kind]
    value = getattr(source, required_field)
    assert value is not None
    return str(value)
