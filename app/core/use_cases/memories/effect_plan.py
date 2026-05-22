"""Typed memory write effect plans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TypeAlias


class EffectType(str, Enum):
    """Supported side effects produced by memory write planners."""

    MEMORY_CREATE = "memory.create"
    MEMORY_EMBEDDING_UPSERT = "memory_embedding.upsert"
    MEMORY_EVIDENCE_ATTACH = "memory_evidence.attach"
    PROBLEM_ATTEMPT_CREATE = "problem_attempt.create"
    MEMORY_LIFECYCLE_UPDATE = "memory.lifecycle_update"
    UTILITY_OBSERVATION_APPEND = "utility_observation.append"
    FACT_UPDATE_CREATE = "fact_update.create"
    ASSOCIATION_UPSERT_AND_OBSERVE = "association.upsert_and_observe"


@dataclass(frozen=True)
class MemoryAddEffectParams:
    memory_id: str
    repo_id: str
    scope: str
    kind: str
    text: str


@dataclass(frozen=True)
class MemoryEmbeddingUpsertEffectParams:
    memory_id: str
    model: str
    text: str


@dataclass(frozen=True)
class MemoryEvidenceAttachEffectParams:
    memory_id: str
    repo_id: str
    refs: tuple[str, ...]


@dataclass(frozen=True)
class ProblemAttemptCreateEffectParams:
    problem_id: str
    attempt_id: str
    role: str


@dataclass(frozen=True)
class EvidenceSourceEffectParams:
    kind: str
    ref: str | None = None
    episode_event_id: str | None = None
    anchor_id: str | None = None
    memory_id: str | None = None
    commit_ref: str | None = None
    transcript_ref: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class MemoryLifecycleUpdateEffectParams:
    event_id: str
    repo_id: str
    memory_id: str
    status: str
    rationale: str
    actor: str
    validated_at: datetime | None
    superseded_by_id: str | None
    evidence: tuple[EvidenceSourceEffectParams, ...]


@dataclass(frozen=True)
class UtilityObservationAppendEffectParams:
    id: str
    repo_id: str
    memory_id: str
    problem_id: str
    vote: float
    rationale: str | None
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class FactUpdateCreateEffectParams:
    id: str
    repo_id: str
    old_fact_id: str
    change_id: str
    new_fact_id: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class AssociationUpsertAndObserveEffectParams:
    repo_id: str
    edge_id: str
    from_memory_id: str
    to_memory_id: str
    relation_type: str
    source_mode: str
    state: str
    strength: float
    observation_id: str
    observation_source: str
    valence: float
    salience: float
    evidence_refs: tuple[str, ...]


EffectParams: TypeAlias = (
    MemoryAddEffectParams
    | MemoryEmbeddingUpsertEffectParams
    | MemoryEvidenceAttachEffectParams
    | ProblemAttemptCreateEffectParams
    | MemoryLifecycleUpdateEffectParams
    | UtilityObservationAppendEffectParams
    | FactUpdateCreateEffectParams
    | AssociationUpsertAndObserveEffectParams
)


@dataclass(frozen=True)
class PlannedEffect:
    """One typed effect planned by a pure policy and executed by a use case."""

    effect_type: EffectType
    params: EffectParams


def make_side_effect(
    effect_type: EffectType | str, params: EffectParams
) -> PlannedEffect:
    """Create a normalized side-effect descriptor object."""

    return PlannedEffect(effect_type=EffectType(effect_type), params=params)
