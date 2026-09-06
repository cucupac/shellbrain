"""Validate and persist memory updates in the caller's transaction."""

from dataclasses import replace

from app.core.errors import DomainValidationError
from app.core.entities.evidence import (
    EvidenceRole,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceTarget,
    EvidenceTargetType,
)
from app.core.entities.memories import (
    MemoryLifecycleActor,
    MemoryLifecycleEvent,
    MemoryLifecycleStatus,
)
from app.core.entities.structural_memory_relations import (
    StructuralMemoryRelation,
    StructuralMemoryRelationPredicate,
)
from app.core.entities.utility import UtilityObservation
from app.core.ports.system.clock import IClock
from app.core.ports.system.idgen import IIdGenerator
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.use_cases.memories.update.request import (
    AssociationLinkUpdate,
    FactUpdateLinkUpdate,
    MemoryBatchUpdateRequest,
    MemoryLifecycleUpdate,
    MemoryUpdateRequest,
    UtilityVoteUpdate,
)
from app.core.use_cases.memories.update.result import (
    BatchUpdateMemoryResult,
    UpdateMemoryResult,
)
from app.core.use_cases.memories.reference_checks import validate_update_request
from app.core.use_cases.memories.writes import (
    MemoryWrite,
    attach_episode_evidence,
    write_association,
)


def execute_update_memory(
    request: MemoryUpdateRequest | MemoryBatchUpdateRequest,
    uow: IUnitOfWork,
    *,
    id_generator: IIdGenerator,
    clock: IClock | None = None,
) -> UpdateMemoryResult | BatchUpdateMemoryResult:
    """Validate the entire request before writing any member of a batch."""

    errors = validate_update_request(request, uow=uow)
    if errors:
        raise DomainValidationError(errors)
    if isinstance(request, MemoryBatchUpdateRequest):
        writes = [
            _write_utility(
                uow,
                repo_id=request.repo_id,
                memory_id=item.memory_id,
                update=item.update,
                id_generator=id_generator,
            )
            for item in request.updates
        ]
        return BatchUpdateMemoryResult(
            problem_id=request.updates[0].update.problem_id,
            updated_memory_ids=[item.memory_id for item in request.updates],
            applied_count=len(request.updates),
            writes=writes,
        )
    update = request.update
    if isinstance(update, UtilityVoteUpdate):
        write = _write_utility(
            uow,
            repo_id=request.repo_id,
            memory_id=request.memory_id,
            update=update,
            id_generator=id_generator,
        )
    elif isinstance(update, AssociationLinkUpdate):
        write = write_association(
            uow,
            repo_id=request.repo_id,
            memory_id=request.memory_id,
            link=update,
            evidence_refs=update.evidence_refs,
            id_generator=id_generator,
        )
    elif isinstance(update, FactUpdateLinkUpdate):
        write = _write_fact_change(
            request, uow, update=update, id_generator=id_generator
        )
    else:
        write = _write_lifecycle(
            request, uow, update=update, id_generator=id_generator, clock=clock
        )
    return UpdateMemoryResult(memory_id=request.memory_id, writes=[write])


def _write_utility(
    uow: IUnitOfWork,
    *,
    repo_id: str,
    memory_id: str,
    update: UtilityVoteUpdate,
    id_generator: IIdGenerator,
) -> MemoryWrite:
    observation_id = id_generator.new_id()
    uow.utility.append_observation(
        UtilityObservation(
            id=observation_id,
            memory_id=memory_id,
            problem_id=update.problem_id,
            vote=update.vote,
            rationale=update.rationale,
        )
    )
    attach_episode_evidence(
        uow,
        repo_id=repo_id,
        target_type=EvidenceTargetType.UTILITY_OBSERVATION,
        target_id=observation_id,
        refs=update.evidence_refs,
    )
    return MemoryWrite(
        "utility_observation.append",
        {
            "id": observation_id,
            "repo_id": repo_id,
            "memory_id": memory_id,
            **update.model_dump(exclude={"type"}),
        },
    )


def _write_fact_change(
    request: MemoryUpdateRequest,
    uow: IUnitOfWork,
    *,
    update: FactUpdateLinkUpdate,
    id_generator: IIdGenerator,
) -> MemoryWrite:
    relation_ids = []
    for subject, predicate, target in (
        (
            update.old_fact_id,
            StructuralMemoryRelationPredicate.SUPERSEDED_BY,
            update.new_fact_id,
        ),
        (
            update.old_fact_id,
            StructuralMemoryRelationPredicate.EXPLAINED_BY_CHANGE,
            request.memory_id,
        ),
        (
            update.new_fact_id,
            StructuralMemoryRelationPredicate.EXPLAINED_BY_CHANGE,
            request.memory_id,
        ),
    ):
        relation = uow.experiences.upsert_structural_memory_relation(
            StructuralMemoryRelation(
                id=id_generator.new_id(),
                repo_id=request.repo_id,
                subject_memory_id=subject,
                predicate=predicate,
                object_memory_id=target,
            )
        )
        relation_ids.append(relation.id)
        attach_episode_evidence(
            uow,
            repo_id=request.repo_id,
            target_type=EvidenceTargetType.STRUCTURAL_MEMORY_RELATION,
            target_id=relation.id,
            refs=update.evidence_refs,
        )
    return MemoryWrite(
        "structural_fact_change.create",
        {
            "repo_id": request.repo_id,
            "change_id": request.memory_id,
            "structural_relation_ids": tuple(relation_ids),
            **update.model_dump(exclude={"type", "rationale"}),
        },
    )


def _write_lifecycle(
    request: MemoryUpdateRequest,
    uow: IUnitOfWork,
    *,
    update: MemoryLifecycleUpdate,
    id_generator: IIdGenerator,
    clock: IClock | None,
) -> MemoryWrite:
    if clock is None:
        raise ValueError("memory lifecycle updates require a clock")
    now = clock.now()
    memory = uow.memories.get(request.memory_id)
    if memory is None:
        raise LookupError(
            f"Target shellbrain not found for lifecycle update: {request.memory_id}"
        )
    status = MemoryLifecycleStatus(update.status)
    actor = MemoryLifecycleActor(update.actor)
    updated = replace(
        memory,
        status=status,
        updated_by=actor,
        validated_at=update.validated_at
        or (now if status is MemoryLifecycleStatus.ACTIVE else memory.validated_at),
        invalidated_at=(memory.invalidated_at or now)
        if status
        in {
            MemoryLifecycleStatus.STALE,
            MemoryLifecycleStatus.SUPERSEDED,
            MemoryLifecycleStatus.WRONG,
        }
        else None,
        superseded_by_id=update.superseded_by_id,
    )
    if not uow.memories.update_lifecycle(updated):
        raise LookupError(
            f"Target shellbrain not found for lifecycle update: {request.memory_id}"
        )
    event_id = id_generator.new_id()
    uow.memories.add_lifecycle_event(
        MemoryLifecycleEvent(
            id=event_id,
            repo_id=request.repo_id,
            memory_id=request.memory_id,
            from_status=memory.status,
            to_status=status,
            rationale=update.rationale,
            actor=actor,
            superseded_by_id=update.superseded_by_id,
            created_at=now,
        )
    )
    uow.evidence.attach_evidence(
        repo_id=request.repo_id,
        target=EvidenceTarget(
            target_type=EvidenceTargetType.MEMORY_LIFECYCLE_EVENT, target_id=event_id
        ),
        sources=tuple(
            EvidenceSource(
                source_kind=EvidenceSourceKind(item.kind),
                **item.model_dump(exclude={"kind"}),
            )
            for item in update.evidence
        ),
        role=EvidenceRole.SUPPORTS,
    )
    return MemoryWrite(
        "memory.lifecycle_update",
        {
            "event_id": event_id,
            "repo_id": request.repo_id,
            "memory_id": request.memory_id,
            **update.model_dump(exclude={"type"}),
        },
    )
