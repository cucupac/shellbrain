"""Memory-record contracts for create execution."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryCreateRequest
from app.core.entities.memory import MemoryKind, MemoryScope
from app.core.interfaces.embeddings import IEmbeddingProvider
from app.core.use_cases.create_memory import execute_create_memory
from app.periphery.db.models.experiences import problem_attempts
from app.periphery.db.models.memories import memories
from app.periphery.db.uow import PostgresUnitOfWork


def test_create_problem_persists_memory_without_problem_attempt(
    uow_factory: Callable[[], PostgresUnitOfWork],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create(problem) should always persist one memory row and no problem_attempt row."""

    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "A problem memory.",
                "scope": "repo",
                "kind": "problem",
                "confidence": 0.8,
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
        )

    assert result.status == "ok"
    memory_id = result.data["memory_id"]
    memory_rows = fetch_rows(memories, memories.c.id == memory_id)
    attempt_rows = fetch_rows(problem_attempts, problem_attempts.c.attempt_id == memory_id)
    assert len(memory_rows) == 1
    assert memory_rows[0]["kind"] == "problem"
    assert len(attempt_rows) == 0


def test_create_solution_persists_problem_attempt_with_solution_role(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create(solution) should always persist one problem_attempt row with role solution."""

    seed_memory(
        memory_id="problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="A seeded problem.",
    )
    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "A candidate solution.",
                "scope": "repo",
                "kind": "solution",
                "confidence": 0.75,
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
        )

    assert result.status == "ok"
    memory_id = result.data["memory_id"]
    rows = fetch_rows(problem_attempts, problem_attempts.c.attempt_id == memory_id)
    assert len(rows) == 1
    assert rows[0]["problem_id"] == "problem-1"
    assert rows[0]["role"] == "solution"


def test_create_failed_tactic_persists_problem_attempt_with_failed_tactic_role(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create(failed_tactic) should always persist one problem_attempt row with role failed_tactic."""

    seed_memory(
        memory_id="problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="A seeded problem.",
    )
    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "A failed tactic.",
                "scope": "repo",
                "kind": "failed_tactic",
                "confidence": 0.6,
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
        )

    assert result.status == "ok"
    memory_id = result.data["memory_id"]
    rows = fetch_rows(problem_attempts, problem_attempts.c.attempt_id == memory_id)
    assert len(rows) == 1
    assert rows[0]["problem_id"] == "problem-1"
    assert rows[0]["role"] == "failed_tactic"
