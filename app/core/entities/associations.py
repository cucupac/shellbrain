"""This module defines formal association entities and association metadata enums."""

from dataclasses import dataclass
from enum import Enum

from app.core.entities.ids import (
    AssociationEdgeId,
    Confidence,
    EpisodeId,
    MemoryId,
    RepoId,
    Salience,
)


class AssociationRelationType(str, Enum):
    """This enum defines ratified formal association relation types."""

    DEPENDS_ON = "depends_on"
    ASSOCIATED_WITH = "associated_with"
    MATURES_INTO = "matures_into"


class AssociationSourceMode(str, Enum):
    """This enum defines whether an association comes from agent or implicit channels."""

    AGENT = "agent"
    IMPLICIT = "implicit"
    MIXED = "mixed"


class AssociationState(str, Enum):
    """This enum defines the lifecycle state of an association edge."""

    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    DEPRECATED = "deprecated"


@dataclass(kw_only=True)
class AssociationEdge:
    """This dataclass models a formal association edge between two memories."""

    id: AssociationEdgeId
    repo_id: RepoId
    from_memory_id: MemoryId
    to_memory_id: MemoryId
    relation_type: AssociationRelationType
    source_mode: AssociationSourceMode = AssociationSourceMode.AGENT
    state: AssociationState = AssociationState.TENTATIVE
    strength: Confidence = Confidence(0.0)


@dataclass(kw_only=True)
class AssociationObservation:
    """This dataclass models an immutable reinforcement observation for associations."""

    id: str
    repo_id: RepoId
    from_memory_id: MemoryId
    to_memory_id: MemoryId
    relation_type: AssociationRelationType
    source: str
    valence: Confidence
    salience: Salience = Salience(0.5)
    edge_id: AssociationEdgeId | None = None
    problem_id: MemoryId | None = None
    episode_id: EpisodeId | None = None
