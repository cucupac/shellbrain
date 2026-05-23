"""Memory-record contracts for create execution."""

from collections.abc import Callable

from app.core.use_cases.memories.add.request import MemoryAddRequest
from app.core.entities.memories import MemoryKind, MemoryScope
from app.core.ports.embeddings.provider import IEmbeddingProvider
from app.core.use_cases.memories.add import execute_create_memory
from tests.operations._shared.id_generators import SequenceIdGenerator
from app.infrastructure.db.runtime.models.experiences import structural_memory_relations
from app.infrastructure.db.runtime.models.memories import memories
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork


def test_create_problem_persists_memory_without_structural_problem_link(
    uow_factory: Callable[[], PostgresUnitOfWork],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create(problem) should persist one shellbrain row and no problem link."""

    request = MemoryAddRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "A problem memory.",
                "scope": "repo",
                "kind": "problem",
                "evidence_refs": ["session://1"],
            },
        }
    )

    with uow_factory() as uow:
        result = execute_create_memory(
            request,
            uow,
            embedding_provider=stub_embedding_provider,
            embedding_model="stub-v1",
            id_generator=SequenceIdGenerator(),
        )
    memory_id = result.data["memory_id"]
    memory_rows = fetch_rows(memories, memories.c.id == memory_id)
    structural_rows = fetch_rows(
        structural_memory_relations,
        structural_memory_relations.c.subject_memory_id == memory_id,
    )
    assert len(memory_rows) == 1
    assert memory_rows[0]["kind"] == "problem"
    assert structural_rows == []


def test_create_solution_persists_structural_solution_relation(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create(solution) should persist one solved_by structural relation."""

    seed_memory(
        memory_id="problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="A seeded problem.",
    )
    request = MemoryAddRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "A candidate solution.",
                "scope": "repo",
                "kind": "solution",
                "links": {"problem_id": "problem-1"},
                "evidence_refs": ["session://1"],
            },
        }
    )

    with uow_factory() as uow:
        result = execute_create_memory(
            request,
            uow,
            embedding_provider=stub_embedding_provider,
            embedding_model="stub-v1",
            id_generator=SequenceIdGenerator(),
        )
    memory_id = result.data["memory_id"]
    relation_rows = fetch_rows(
        structural_memory_relations,
        structural_memory_relations.c.subject_memory_id == "problem-1",
        structural_memory_relations.c.object_memory_id == memory_id,
    )
    assert len(relation_rows) == 1
    assert relation_rows[0]["predicate"] == "solved_by"


def test_create_failed_tactic_persists_structural_failed_with_relation(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create(failed_tactic) should persist one failed_with structural relation."""

    seed_memory(
        memory_id="problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="A seeded problem.",
    )
    request = MemoryAddRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "A failed tactic.",
                "scope": "repo",
                "kind": "failed_tactic",
                "links": {"problem_id": "problem-1"},
                "evidence_refs": ["session://1"],
            },
        }
    )

    with uow_factory() as uow:
        result = execute_create_memory(
            request,
            uow,
            embedding_provider=stub_embedding_provider,
            embedding_model="stub-v1",
            id_generator=SequenceIdGenerator(),
        )
    memory_id = result.data["memory_id"]
    relation_rows = fetch_rows(
        structural_memory_relations,
        structural_memory_relations.c.subject_memory_id == "problem-1",
        structural_memory_relations.c.object_memory_id == memory_id,
    )
    assert len(relation_rows) == 1
    assert relation_rows[0]["predicate"] == "failed_with"
