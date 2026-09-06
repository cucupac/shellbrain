"""Validate and persist one memory with its evidence and links."""

from app.core.errors import DomainValidationError
from app.core.entities.evidence import EvidenceTargetType
from app.core.entities.memories import Memory, MemoryKind, MemoryScope
from app.core.entities.structural_memory_relations import (
    StructuralMemoryRelation,
    predicate_for_problem_link_kind,
)
from app.core.ports.embeddings.provider import IEmbeddingProvider
from app.core.ports.system.idgen import IIdGenerator
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.use_cases.memories.add.request import MemoryAddRequest
from app.core.use_cases.memories.add.result import CreateMemoryResult
from app.core.use_cases.memories.reference_checks import validate_create_request
from app.core.use_cases.memories.writes import (
    MemoryWrite,
    attach_episode_evidence,
    write_association,
)


def execute_create_memory(
    request: MemoryAddRequest,
    uow: IUnitOfWork,
    *,
    embedding_provider: IEmbeddingProvider,
    embedding_model: str,
    id_generator: IIdGenerator,
) -> CreateMemoryResult:
    """Write a validated memory inside the caller's transaction."""

    errors = validate_create_request(request, uow=uow)
    if errors:
        raise DomainValidationError(errors)
    body = request.memory
    memory_id = id_generator.new_id()
    repo_id = request.repo_id
    refs = tuple(body.evidence_refs)
    uow.memories.create(
        Memory(
            id=memory_id,
            repo_id=repo_id,
            scope=MemoryScope(body.scope),
            kind=MemoryKind(body.kind),
            text=body.text,
        )
    )
    uow.memories.upsert_embedding(
        memory_id=memory_id,
        model=embedding_model,
        vector=embedding_provider.embed(body.text),
    )
    attach_episode_evidence(
        uow,
        repo_id=repo_id,
        target_type=EvidenceTargetType.MEMORY,
        target_id=memory_id,
        refs=refs,
    )
    writes = [
        MemoryWrite(
            "memory.create",
            {
                "memory_id": memory_id,
                "repo_id": repo_id,
                "scope": body.scope,
                "kind": body.kind,
            },
        ),
        MemoryWrite(
            "memory_embedding.upsert",
            {"memory_id": memory_id, "model": embedding_model},
        ),
        MemoryWrite(
            "evidence.attach",
            {"memory_id": memory_id, "repo_id": repo_id, "refs": refs},
        ),
    ]
    if MemoryKind(body.kind).requires_problem_link and body.links.problem_id:
        relation = uow.experiences.upsert_structural_memory_relation(
            StructuralMemoryRelation(
                id=id_generator.new_id(),
                repo_id=repo_id,
                subject_memory_id=body.links.problem_id,
                predicate=predicate_for_problem_link_kind(body.kind),
                object_memory_id=memory_id,
            )
        )
        attach_episode_evidence(
            uow,
            repo_id=repo_id,
            target_type=EvidenceTargetType.STRUCTURAL_MEMORY_RELATION,
            target_id=relation.id,
            refs=refs,
        )
        writes.append(
            MemoryWrite(
                "structural_problem_link.create",
                {
                    "relation_id": relation.id,
                    "repo_id": repo_id,
                    "problem_id": body.links.problem_id,
                    "attempt_id": memory_id,
                    "attempt_kind": body.kind,
                    "evidence_refs": refs,
                },
            )
        )
    for link in body.links.associations:
        writes.append(
            write_association(
                uow,
                repo_id=repo_id,
                memory_id=memory_id,
                link=link,
                evidence_refs=refs,
                id_generator=id_generator,
            )
        )
    return CreateMemoryResult(memory_id=memory_id, writes=writes)
