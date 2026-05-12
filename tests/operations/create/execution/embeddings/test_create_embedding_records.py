"""Embedding-record contracts for create execution."""

from collections.abc import Callable

from app.core.use_cases.memories.add.request import MemoryAddRequest
from app.core.ports.embeddings.provider import IEmbeddingProvider
from app.core.use_cases.memories.add import execute_create_memory
from tests.operations._shared.id_generators import SequenceIdGenerator
from app.infrastructure.db.runtime.models.memories import memory_embeddings
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork


def test_create_persists_memory_embedding_row(
    uow_factory: Callable[[], PostgresUnitOfWork],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """create should always persist one memory_embedding row for the new memory."""

    request = MemoryAddRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Embedding target memory.",
                "scope": "repo",
                "kind": "fact",
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
    rows = fetch_rows(memory_embeddings, memory_embeddings.c.memory_id == memory_id)
    assert len(rows) == 1
    assert rows[0]["model"] == "stub-v1"
    assert rows[0]["dim"] == 4
