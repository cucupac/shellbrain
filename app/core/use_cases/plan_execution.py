"""This module defines shared side-effect execution for create and update policies."""

from app.core.entities.associations import (
    AssociationEdge,
    AssociationObservation,
    AssociationRelationType,
    AssociationSourceMode,
    AssociationState,
)
from app.core.entities.facts import FactUpdate, ProblemAttempt, ProblemAttemptRole
from app.core.entities.memories import Memory, MemoryKind, MemoryScope
from app.core.entities.utility import UtilityObservation
from app.core.use_cases.memories.effect_plan import (
    AssociationUpsertAndObserveEffectParams,
    EffectType,
    FactUpdateCreateEffectParams,
    MemoryArchiveStateEffectParams,
    MemoryAddEffectParams,
    MemoryEmbeddingUpsertEffectParams,
    MemoryEvidenceAttachEffectParams,
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
            for ref in sorted(params.refs):
                evidence = uow.evidence.upsert_ref(repo_id=params.repo_id, ref=ref)
                uow.evidence.link_memory_evidence(
                    memory_id=params.memory_id, evidence_id=evidence.id
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

        if effect_type is EffectType.MEMORY_ARCHIVE_STATE:
            assert isinstance(params, MemoryArchiveStateEffectParams)
            updated = uow.memories.set_archived(
                memory_id=params.memory_id, archived=params.archived
            )
            if not updated:
                raise LookupError(
                    f"Target shellbrain not found for archive update: {params.memory_id}"
                )
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
            for ref in sorted(params.evidence_refs):
                evidence = uow.evidence.upsert_ref(repo_id=params.repo_id, ref=ref)
                uow.evidence.link_association_edge_evidence(
                    edge_id=edge.id, evidence_id=evidence.id
                )
            continue

        raise ValueError(f"Unsupported side effect type: {effect_type}")
