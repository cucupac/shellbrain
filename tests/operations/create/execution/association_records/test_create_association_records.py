"""Association-record contracts for create execution."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryCreateRequest
from app.core.entities.memory import MemoryKind, MemoryScope
from app.core.interfaces.embeddings import IEmbeddingProvider
from app.core.use_cases.memories.create_memory import execute_create_memory
from app.infrastructure.db.models.associations import association_edges, association_observations
from app.infrastructure.db.uow import PostgresUnitOfWork


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
