"""Transaction execution contracts for accepted write operations."""

from collections.abc import Callable

import pytest

from app.core.contracts.requests import MemoryCreateRequest
from app.core.interfaces.embeddings import IEmbeddingProvider
from app.core.use_cases.create_memory import execute_create_memory
from app.periphery.db.uow import PostgresUnitOfWork


class _FailingEmbeddingProvider(IEmbeddingProvider):
    """Embedding provider that fails during side-effect execution."""

    def embed(self, text: str) -> list[float]:
        _ = text
        raise RuntimeError("embedding failed")


def test_side_effect_failure_mid_write_rolls_back_all_prior_effects(
    uow_factory: Callable[[], PostgresUnitOfWork],
    count_rows: Callable[[str], int],
) -> None:
    """mid-write side-effect failures should always roll back all prior side effects."""

    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Create memory with failing embedding side effect.",
                "scope": "repo",
                "kind": "problem",
                "confidence": 0.8,
                "evidence_refs": ["session://1"],
            },
        }
    )

    with pytest.raises(RuntimeError, match="embedding failed"):
        with uow_factory() as uow:
            execute_create_memory(
                request,
                uow,
                embedding_provider=_FailingEmbeddingProvider(),
                embedding_model="failing-v1",
            )

    assert count_rows("memories") == 0
    assert count_rows("memory_embeddings") == 0
    assert count_rows("memory_evidence") == 0
    assert count_rows("evidence_refs") == 0
