"""Transaction contracts for write-path validation."""

from collections.abc import Callable

from app.core.contracts.requests import MemoryCreateRequest
from app.core.interfaces.embeddings import IEmbeddingProvider
from app.core.use_cases.create_memory import execute_create_memory
from app.periphery.cli.handlers import handle_create
from app.periphery.db.uow import PostgresUnitOfWork


class _FailingEmbeddingProvider(IEmbeddingProvider):
    """Embedding provider that fails during encode."""

    def embed(self, text: str) -> list[float]:
        _ = text
        raise RuntimeError("embedding failed")


def test_validation_failure_writes_nothing(
    uow_factory: Callable[[], PostgresUnitOfWork],
    stub_embedding_provider: IEmbeddingProvider,
    count_rows: Callable[[str], int],
) -> None:
    """validation failure should always write nothing."""

    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Invalid solution payload.",
                "scope": "repo",
                "kind": "solution",
                "confidence": 0.7,
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

    assert result.status == "error"
    assert count_rows("memories") == 0
    assert count_rows("memory_embeddings") == 0
    assert count_rows("memory_evidence") == 0


def test_embedding_failure_writes_nothing(
    uow_factory: Callable[[], PostgresUnitOfWork],
    count_rows: Callable[[str], int],
) -> None:
    """embedding failure should always write nothing."""

    payload = {
        "op": "create",
        "repo_id": "repo-a",
        "memory": {
            "text": "Create path with failing embedding.",
            "scope": "repo",
            "kind": "problem",
            "confidence": 0.7,
            "evidence_refs": ["session://1"],
        },
    }

    result = handle_create(
        payload,
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: _FailingEmbeddingProvider(),
        embedding_model="failing-v1",
    )

    assert result["status"] == "error"
    assert count_rows("memories") == 0
    assert count_rows("memory_embeddings") == 0
    assert count_rows("memory_evidence") == 0
