"""Evidence-link contracts for create execution."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryCreateRequest
from app.core.entities.memory import MemoryKind, MemoryScope
from app.core.interfaces.embeddings import IEmbeddingProvider
from app.core.use_cases.create_memory import execute_create_memory
from app.periphery.db.models.associations import association_edge_evidence, association_edges
from app.periphery.db.models.evidence import evidence_refs
from app.periphery.db.models.memories import memory_evidence
from app.periphery.db.uow import PostgresUnitOfWork


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
