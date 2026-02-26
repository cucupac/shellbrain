"""This integration test validates that create writes embedding rows into PostgreSQL."""

import os

import pytest
from sqlalchemy import select, text

from app.core.contracts.requests import MemoryCreateRequest
from app.core.use_cases.create_memory import execute_create_memory
from app.periphery.db.engine import get_engine
from app.periphery.embeddings.local_provider import SentenceTransformersEmbeddingProvider
from app.periphery.db.models.memories import memory_embeddings
from app.periphery.db.models.registry import target_metadata
from app.periphery.db.session import get_session_factory
from app.periphery.db.uow import PostgresUnitOfWork


def test_create_persists_memory_embedding_row() -> None:
    """This test verifies create inserts a memory_embedding row from the local sentence-transformers provider."""

    dsn = os.getenv("MEMORY_DB_DSN_TEST")
    if not dsn:
        pytest.skip("Set MEMORY_DB_DSN_TEST to run PostgreSQL integration tests.")

    engine = get_engine(dsn)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    target_metadata.drop_all(bind=engine)
    target_metadata.create_all(bind=engine)

    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-integration",
            "memory": {
                "text": "Integration test memory",
                "scope": "repo",
                "kind": "problem",
                "confidence": 0.8,
                "evidence_refs": ["integration://evidence/1"],
            },
        }
    )

    provider = SentenceTransformersEmbeddingProvider(model="all-MiniLM-L6-v2")

    with PostgresUnitOfWork(get_session_factory(engine)) as uow:
        result = execute_create_memory(
            request,
            uow,
            embedding_provider=provider,
            embedding_model="all-MiniLM-L6-v2",
        )

    assert result.status == "ok"
    memory_id = result.data["memory_id"]
    with engine.connect() as conn:
        row = conn.execute(
            select(memory_embeddings.c.model, memory_embeddings.c.dim).where(memory_embeddings.c.memory_id == memory_id)
        ).mappings().first()
    assert row is not None
    assert row["model"] == "all-MiniLM-L6-v2"
    assert row["dim"] == 384
