"""This module defines evidence reference entities and evidence link entities."""

from dataclasses import dataclass


@dataclass(kw_only=True)
class EvidenceRef:
    """This dataclass models a canonical evidence reference entry."""

    id: str
    repo_id: str
    ref: str
    episode_event_id: str | None = None


@dataclass(kw_only=True)
class MemoryEvidenceLink:
    """This dataclass models a many-to-many link between memory and evidence."""

    memory_id: str
    evidence_id: str


@dataclass(kw_only=True)
class AssociationEdgeEvidenceLink:
    """This dataclass models a many-to-many link between association edges and evidence."""

    edge_id: str
    evidence_id: str
