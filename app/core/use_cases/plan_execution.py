"""This module defines shared side-effect execution for create and update policies."""

from dataclasses import replace
from datetime import datetime

from app.core.entities.associations import (
    AssociationEdge,
    AssociationObservation,
    AssociationRelationType,
    AssociationSourceMode,
    AssociationState,
)
from app.core.entities.evidence import (
    EvidenceRole,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceTarget,
    EvidenceTargetType,
)
from app.core.entities.facts import FactUpdate, ProblemAttempt, ProblemAttemptRole
from app.core.entities.memories import (
    Memory,
    MemoryKind,
    MemoryScope,
    MemoryLifecycleActor,
    MemoryLifecycleEvent,
    MemoryLifecycleStatus,
)
from app.core.entities.utility import UtilityObservation
from app.core.use_cases.memories.effect_plan import (
    AssociationUpsertAndObserveEffectParams,
    EvidenceSourceEffectParams,
    EffectType,
    FactUpdateCreateEffectParams,
    MemoryAddEffectParams,
    MemoryEmbeddingUpsertEffectParams,
    MemoryEvidenceAttachEffectParams,
    MemoryLifecycleUpdateEffectParams,
    PlannedEffect,
    ProblemAttemptCreateEffectParams,
    UtilityObservationAppendEffectParams,
)
from app.core.ports.embeddings.provider import IEmbeddingProvider
from app.core.ports.db.unit_of_work import IUnitOfWork


def apply_side_effects(
    plan: list[PlannedEffect],
    uow: IUnitOfWork,
    *,
    embedding_provider: IEmbeddingProvider | None = None,
    now: datetime | None = None,
) -> None:
    """This function executes a deterministic side-effect plan inside one transaction."""

    for effect in plan:
        effect_type = effect.effect_type
        params = effect.params

        if effect_type is EffectType.MEMORY_CREATE:
            assert isinstance(params, MemoryAddEffectParams)
            uow.memories.create(
                Memory(
                    id=params.memory_id,
                    repo_id=params.repo_id,
                    scope=MemoryScope(params.scope),
                    kind=MemoryKind(params.kind),
                    text=params.text,
                )
            )
            continue

        if effect_type is EffectType.MEMORY_EMBEDDING_UPSERT:
            assert isinstance(params, MemoryEmbeddingUpsertEffectParams)
            if embedding_provider is None:
                raise RuntimeError(
                    "Embedding provider is required for memory_embedding.upsert"
                )
            uow.memories.upsert_embedding(
                memory_id=params.memory_id,
                model=params.model,
                vector=embedding_provider.embed(params.text),
            )
            continue

        if effect_type is EffectType.MEMORY_EVIDENCE_ATTACH:
            assert isinstance(params, MemoryEvidenceAttachEffectParams)
            _attach_episode_event_evidence(
                uow,
                repo_id=params.repo_id,
                target_type=EvidenceTargetType.MEMORY,
                target_id=params.memory_id,
                refs=params.refs,
            )
            continue

        if effect_type is EffectType.PROBLEM_ATTEMPT_CREATE:
            assert isinstance(params, ProblemAttemptCreateEffectParams)
            uow.experiences.create_problem_attempt(
                ProblemAttempt(
                    problem_id=params.problem_id,
                    attempt_id=params.attempt_id,
                    role=ProblemAttemptRole(params.role),
                )
            )
            continue

        if effect_type is EffectType.MEMORY_LIFECYCLE_UPDATE:
            assert isinstance(params, MemoryLifecycleUpdateEffectParams)
            _apply_memory_lifecycle_update(uow, params=params, now=now)
            continue

        if effect_type is EffectType.UTILITY_OBSERVATION_APPEND:
            assert isinstance(params, UtilityObservationAppendEffectParams)
            uow.utility.append_observation(
                UtilityObservation(
                    id=params.id,
                    memory_id=params.memory_id,
                    problem_id=params.problem_id,
                    vote=float(params.vote),
                    rationale=params.rationale,
                )
            )
            _attach_episode_event_evidence(
                uow,
                repo_id=params.repo_id,
                target_type=EvidenceTargetType.UTILITY_OBSERVATION,
                target_id=params.id,
                refs=params.evidence_refs,
            )
            continue

        if effect_type is EffectType.FACT_UPDATE_CREATE:
            assert isinstance(params, FactUpdateCreateEffectParams)
            uow.experiences.create_fact_update(
                FactUpdate(
                    id=params.id,
                    old_fact_id=params.old_fact_id,
                    change_id=params.change_id,
                    new_fact_id=params.new_fact_id,
                )
            )
            _attach_episode_event_evidence(
                uow,
                repo_id=params.repo_id,
                target_type=EvidenceTargetType.FACT_UPDATE,
                target_id=params.id,
                refs=params.evidence_refs,
            )
            continue

        if effect_type is EffectType.ASSOCIATION_UPSERT_AND_OBSERVE:
            assert isinstance(params, AssociationUpsertAndObserveEffectParams)
            edge = uow.associations.upsert_edge(
                AssociationEdge(
                    id=params.edge_id,
                    repo_id=params.repo_id,
                    from_memory_id=params.from_memory_id,
                    to_memory_id=params.to_memory_id,
                    relation_type=AssociationRelationType(params.relation_type),
                    source_mode=AssociationSourceMode(params.source_mode),
                    state=AssociationState(params.state),
                    strength=float(params.strength),
                )
            )
            uow.associations.append_observation(
                AssociationObservation(
                    id=params.observation_id,
                    repo_id=params.repo_id,
                    edge_id=edge.id,
                    from_memory_id=params.from_memory_id,
                    to_memory_id=params.to_memory_id,
                    relation_type=AssociationRelationType(params.relation_type),
                    source=params.observation_source,
                    valence=float(params.valence),
                    salience=float(params.salience),
                )
            )
            _attach_episode_event_evidence(
                uow,
                repo_id=params.repo_id,
                target_type=EvidenceTargetType.ASSOCIATION_EDGE,
                target_id=edge.id,
                refs=params.evidence_refs,
            )
            continue

        raise ValueError(f"Unsupported side effect type: {effect_type}")


def _attach_episode_event_evidence(
    uow: IUnitOfWork,
    *,
    repo_id: str,
    target_type: EvidenceTargetType,
    target_id: str,
    refs: tuple[str, ...],
) -> None:
    """Attach episode-event evidence refs through the unified evidence port."""

    uow.evidence.attach_evidence(
        repo_id=repo_id,
        target=EvidenceTarget(target_type=target_type, target_id=target_id),
        sources=tuple(
            EvidenceSource(source_kind=EvidenceSourceKind.EPISODE_EVENT, ref=ref)
            for ref in sorted(refs)
        ),
        role=EvidenceRole.SUPPORTS,
    )


def _apply_memory_lifecycle_update(
    uow: IUnitOfWork,
    *,
    params: MemoryLifecycleUpdateEffectParams,
    now: datetime | None,
) -> None:
    """Apply one auditable memory lifecycle transition."""

    if now is None:
        raise ValueError("memory lifecycle updates require a timestamp")
    memory = uow.memories.get(params.memory_id)
    if memory is None:
        raise LookupError(
            f"Target shellbrain not found for lifecycle update: {params.memory_id}"
        )
    status = MemoryLifecycleStatus(params.status)
    replacement_id = (
        params.superseded_by_id
        if status is MemoryLifecycleStatus.SUPERSEDED
        else None
    )
    updated_memory = replace(
        memory,
        status=status,
        validated_at=_memory_validated_at_for_update(
            status=status,
            action_validated_at=params.validated_at,
            current_validated_at=memory.validated_at,
            now=now,
        ),
        invalidated_at=_memory_invalidated_at_for_update(
            status=status,
            current_invalidated_at=memory.invalidated_at,
            now=now,
        ),
        superseded_by_id=replacement_id,
        updated_by=MemoryLifecycleActor(params.actor),
    )
    if not uow.memories.update_lifecycle(updated_memory):
        raise LookupError(
            f"Target shellbrain not found for lifecycle update: {params.memory_id}"
        )
    uow.memories.add_lifecycle_event(
        MemoryLifecycleEvent(
            id=params.event_id,
            repo_id=params.repo_id,
            memory_id=params.memory_id,
            from_status=memory.status,
            to_status=status,
            rationale=params.rationale,
            actor=MemoryLifecycleActor(params.actor),
            superseded_by_id=replacement_id,
            created_at=now,
        )
    )
    uow.evidence.attach_evidence(
        repo_id=params.repo_id,
        target=EvidenceTarget(
            target_type=EvidenceTargetType.MEMORY_LIFECYCLE_EVENT,
            target_id=params.event_id,
        ),
        sources=tuple(_evidence_source_from_params(item) for item in params.evidence),
        role=EvidenceRole.SUPPORTS,
    )


def _memory_validated_at_for_update(
    *,
    status: MemoryLifecycleStatus,
    action_validated_at: datetime | None,
    current_validated_at: datetime | None,
    now: datetime,
) -> datetime | None:
    if action_validated_at is not None:
        return action_validated_at
    if status is MemoryLifecycleStatus.ACTIVE:
        return now
    return current_validated_at


def _memory_invalidated_at_for_update(
    *,
    status: MemoryLifecycleStatus,
    current_invalidated_at: datetime | None,
    now: datetime,
) -> datetime | None:
    if status in {
        MemoryLifecycleStatus.STALE,
        MemoryLifecycleStatus.SUPERSEDED,
        MemoryLifecycleStatus.WRONG,
    }:
        return current_invalidated_at or now
    return None


def _evidence_source_from_params(params: EvidenceSourceEffectParams) -> EvidenceSource:
    """Convert one planned evidence source into the domain evidence entity."""

    return EvidenceSource(
        source_kind=EvidenceSourceKind(params.kind),
        ref=params.ref,
        episode_event_id=params.episode_event_id,
        anchor_id=params.anchor_id,
        memory_id=params.memory_id,
        commit_ref=params.commit_ref,
        transcript_ref=params.transcript_ref,
        note=params.note,
    )
