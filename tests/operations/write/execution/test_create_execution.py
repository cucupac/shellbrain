"""Create execution contracts for write-path side effects."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryCreateRequest
from app.core.entities.memory import MemoryKind, MemoryScope
from app.core.interfaces.embeddings import IEmbeddingProvider
from app.core.use_cases.create_memory import execute_create_memory
from app.periphery.db.models.associations import association_edge_evidence, association_edges, association_observations
from app.periphery.db.models.evidence import evidence_refs
from app.periphery.db.models.experiences import problem_attempts
from app.periphery.db.models.memories import memories, memory_embeddings, memory_evidence
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


def test_create_persists_memory_embedding_row(
    uow_factory: Callable[[], PostgresUnitOfWork],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create should always persist one memory_embedding row for the new memory."""

    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Embedding target memory.",
                "scope": "repo",
                "kind": "fact",
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
    rows = fetch_rows(memory_embeddings, memory_embeddings.c.memory_id == memory_id)
    assert len(rows) == 1
    assert rows[0]["model"] == "stub-v1"
    assert rows[0]["dim"] == 4


def test_create_attaches_all_memory_evidence_refs_exactly_once(
    uow_factory: Callable[[], PostgresUnitOfWork],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create should always attach each evidence ref exactly once in memory_evidence."""

    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Evidence attachment memory.",
                "scope": "repo",
                "kind": "preference",
                "confidence": 0.9,
                "evidence_refs": ["session://1", "session://2"],
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
    link_rows = fetch_rows(memory_evidence, memory_evidence.c.memory_id == memory_id)
    assert len(link_rows) == 2

    refs = fetch_rows(evidence_refs, evidence_refs.c.repo_id == "repo-a")
    assert {row["ref"] for row in refs} == {"session://1", "session://2"}


def test_create_association_links_persist_edge_and_observation(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create with associations should always persist association_edge and association_observation rows."""

    seed_memory(
        memory_id="target-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Association target.",
    )
    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Association source memory.",
                "scope": "repo",
                "kind": "problem",
                "confidence": 0.8,
                "links": {
                    "associations": [
                        {
                            "to_memory_id": "target-1",
                            "relation_type": "depends_on",
                        }
                    ]
                },
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
    edges = fetch_rows(
        association_edges,
        association_edges.c.repo_id == "repo-a",
        association_edges.c.from_memory_id == memory_id,
        association_edges.c.to_memory_id == "target-1",
        association_edges.c.relation_type == "depends_on",
    )
    assert len(edges) == 1
    observations = fetch_rows(
        association_observations,
        association_observations.c.edge_id == edges[0]["id"],
    )
    assert len(observations) == 1


def test_create_association_links_attach_edge_evidence(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create with associations should always link evidence refs in association_edge_evidence."""

    seed_memory(
        memory_id="target-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Association target.",
    )
    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Association source memory.",
                "scope": "repo",
                "kind": "problem",
                "confidence": 0.8,
                "links": {
                    "associations": [
                        {
                            "to_memory_id": "target-1",
                            "relation_type": "associated_with",
                        }
                    ]
                },
                "evidence_refs": ["session://1", "session://2"],
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
    edges = fetch_rows(
        association_edges,
        association_edges.c.repo_id == "repo-a",
        association_edges.c.from_memory_id == memory_id,
        association_edges.c.to_memory_id == "target-1",
        association_edges.c.relation_type == "associated_with",
    )
    assert len(edges) == 1

    edge_id = str(edges[0]["id"])
    edge_evidence_rows = fetch_rows(
        association_edge_evidence,
        association_edge_evidence.c.edge_id == edge_id,
    )
    assert len(edge_evidence_rows) == 2
