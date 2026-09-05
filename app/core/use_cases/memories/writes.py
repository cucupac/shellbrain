"""Shared memory writes and their completed diagnostic records."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from app.core.entities.associations import (
    AssociationEdge,
    AssociationObservation,
    AssociationRelationType,
)
from app.core.entities.evidence import (
    EvidenceRole,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceTarget,
    EvidenceTargetType,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.system.idgen import IIdGenerator

if TYPE_CHECKING:
    from app.core.use_cases.memories.add.request import MemoryAddAssociationLink
    from app.core.use_cases.memories.update.request import AssociationLinkUpdate


@dataclass(frozen=True)
class MemoryWrite:
    """Diagnostic metadata for a completed write; never an executable instruction."""

    effect_type: Literal[
        "memory.create",
        "memory_embedding.upsert",
        "evidence.attach",
        "structural_problem_link.create",
        "memory.lifecycle_update",
        "utility_observation.append",
        "structural_fact_change.create",
        "association.upsert_and_observe",
    ]
    params: dict[str, Any]


def attach_episode_evidence(
    uow: IUnitOfWork,
    *,
    repo_id: str,
    target_type: EvidenceTargetType,
    target_id: str,
    refs: Sequence[str],
) -> None:
    """Attach validated episode evidence to one written record."""

    uow.evidence.attach_evidence(
        repo_id=repo_id,
        target=EvidenceTarget(target_type=target_type, target_id=target_id),
        sources=tuple(
            EvidenceSource(source_kind=EvidenceSourceKind.EPISODE_EVENT, ref=ref)
            for ref in sorted(refs)
        ),
        role=EvidenceRole.SUPPORTS,
    )


def write_association(
    uow: IUnitOfWork,
    *,
    repo_id: str,
    memory_id: str,
    link: MemoryAddAssociationLink | AssociationLinkUpdate,
    evidence_refs: Sequence[str],
    id_generator: IIdGenerator,
) -> MemoryWrite:
    """Write an association and its observation once for both add and update."""

    edge = uow.associations.upsert_edge(
        AssociationEdge(
            id=id_generator.new_id(),
            repo_id=repo_id,
            from_memory_id=memory_id,
            to_memory_id=link.to_memory_id,
            relation_type=AssociationRelationType(link.relation_type),
            strength=link.confidence,
        )
    )
    observation_id = id_generator.new_id()
    uow.associations.append_observation(
        AssociationObservation(
            id=observation_id,
            repo_id=repo_id,
            edge_id=edge.id,
            from_memory_id=memory_id,
            to_memory_id=link.to_memory_id,
            relation_type=edge.relation_type,
            source="agent_explicit",
            valence=link.confidence,
            salience=link.salience,
        )
    )
    attach_episode_evidence(
        uow,
        repo_id=repo_id,
        target_type=EvidenceTargetType.ASSOCIATION_EDGE,
        target_id=edge.id,
        refs=evidence_refs,
    )
    return MemoryWrite(
        "association.upsert_and_observe",
        {
            "repo_id": repo_id,
            "edge_id": edge.id,
            "from_memory_id": memory_id,
            "to_memory_id": link.to_memory_id,
            "relation_type": link.relation_type,
            "source_mode": edge.source_mode.value,
            "state": edge.state.value,
            "strength": link.confidence,
            "observation_id": observation_id,
            "observation_source": "agent_explicit",
            "valence": link.confidence,
            "salience": link.salience,
            "evidence_refs": tuple(evidence_refs),
        },
    )
