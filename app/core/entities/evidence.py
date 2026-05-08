"""This module defines evidence reference entities and evidence link entities."""

from dataclasses import dataclass

from app.core.entities.ids import AssociationEdgeId, EvidenceId, EvidenceRefText, MemoryId, RepoId


@dataclass(kw_only=True)
class EvidenceRef:
    """This dataclass models a canonical evidence reference entry."""

    id: EvidenceId
    repo_id: RepoId
    ref: EvidenceRefText
    episode_event_id: str | None = None


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
