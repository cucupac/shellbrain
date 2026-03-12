"""Embedding persistence contracts for create execution."""

import os
from pathlib import Path
import subprocess

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


@pytest.mark.real_embedding
def test_create_persists_memory_embedding_row() -> None:
    """create should always persist a memory_embedding row in PostgreSQL when real embeddings are enabled."""

    dsn = os.getenv("MEMORY_DB_DSN_TEST")
    if not dsn:
        pytest.skip("Set MEMORY_DB_DSN_TEST to run PostgreSQL integration tests.")

    engine = get_engine(dsn)
    _run_alembic_upgrade(dsn)
    with engine.begin() as conn:
        table_names = [table.name for table in reversed(target_metadata.sorted_tables)]
        if table_names:
            joined = ", ".join(table_names)
            conn.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE;"))

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


def _run_alembic_upgrade(dsn: str) -> None:
    """This helper applies latest alembic schema before integration assertions."""

    repo_root = Path(__file__).resolve().parents[5]
    env = dict(os.environ)
    env["MEMORY_DB_DSN"] = dsn
    subprocess.run(
        ["alembic", "upgrade", "head"],
        check=True,
        cwd=repo_root,
        env=env,
    )
