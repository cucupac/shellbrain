"""Embedding persistence contracts for create execution."""

import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import select, text

from app.core.entities.episodes import Episode, EpisodeEvent, EpisodeEventSource, EpisodeStatus
from app.core.contracts.requests import MemoryCreateRequest
from app.core.use_cases.create_memory import execute_create_memory
from app.periphery.db.engine import get_engine
from app.periphery.embeddings.local_provider import SentenceTransformersEmbeddingProvider
from app.periphery.db.models.episodes import episode_events, episodes
from app.periphery.db.models.memories import memory_embeddings
from app.periphery.db.models.registry import target_metadata
from app.periphery.db.session import get_session_factory
from app.periphery.db.uow import PostgresUnitOfWork
from tests.operations._shared.destructive_guardrail_fixtures import (
    assert_destructive_test_setup_allowed,
    assert_test_database_is_disposable,
    stamp_test_instance,
)


@pytest.mark.real_embedding
def test_create_persists_memory_embedding_row() -> None:
    """create should always persist a memory_embedding row in PostgreSQL when real embeddings are enabled."""

    dsn = os.getenv("SHELLBRAIN_DB_DSN_TEST")
    if not dsn:
        pytest.skip("Set SHELLBRAIN_DB_DSN_TEST to run PostgreSQL integration tests.")

    assert_test_database_is_disposable(dsn)
    engine = get_engine(dsn)
    _run_alembic_upgrade(dsn)
    stamp_test_instance(dsn)
    assert_destructive_test_setup_allowed(dsn)
    admin_dsn = os.getenv("SHELLBRAIN_DB_ADMIN_DSN_TEST") or os.getenv("SHELLBRAIN_DB_ADMIN_DSN") or dsn
    cleanup_engine = get_engine(admin_dsn)
    try:
        with cleanup_engine.begin() as conn:
            table_names = [
                table.name
                for table in reversed(target_metadata.sorted_tables)
                if table.name != "instance_metadata"
            ]
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
                    "evidence_refs": ["integration://evidence/1"],
                },
            }
        )

        provider = SentenceTransformersEmbeddingProvider(model="all-MiniLM-L6-v2")

        with PostgresUnitOfWork(get_session_factory(engine)) as uow:
            uow.episodes.create_episode(
                Episode(
                    id="repo-integration-episode",
                    repo_id="repo-integration",
                    host_app="codex",
                    thread_id="codex:repo-integration-evidence",
                    status=EpisodeStatus.ACTIVE,
                )
            )
            uow.episodes.append_event(
                EpisodeEvent(
                    id="integration://evidence/1",
                    episode_id="repo-integration-episode",
                    seq=1,
                    host_event_key="integration://evidence/1",
                    source=EpisodeEventSource.USER,
                    content='{"content_text":"integration evidence"}',
                )
            )
            result = execute_create_memory(
                request,
                uow,
                embedding_provider=provider,
                embedding_model="all-MiniLM-L6-v2",
            )

        assert result.status == "ok"
        memory_id = result.data["memory_id"]
        with engine.connect() as conn:
            evidence_row = conn.execute(
                select(episodes.c.id).where(episodes.c.id == "repo-integration-episode")
            ).first()
            event_row = conn.execute(
                select(episode_events.c.id).where(episode_events.c.id == "integration://evidence/1")
            ).first()
            row = conn.execute(
                select(memory_embeddings.c.model, memory_embeddings.c.dim).where(
                    memory_embeddings.c.memory_id == memory_id
                )
            ).mappings().first()
        assert evidence_row is not None
        assert event_row is not None
        assert row is not None
        assert row["model"] == "all-MiniLM-L6-v2"
        assert row["dim"] == 384
    finally:
        cleanup_engine.dispose()


def _run_alembic_upgrade(dsn: str) -> None:
    """This helper applies packaged schema migrations before integration assertions."""

    repo_root = Path(__file__).resolve().parents[5]
    env = dict(os.environ)
    env["SHELLBRAIN_DB_DSN"] = dsn
    env["SHELLBRAIN_DB_ADMIN_DSN"] = os.getenv("SHELLBRAIN_DB_ADMIN_DSN_TEST", dsn)
    env["SHELLBRAIN_INSTANCE_MODE"] = "test"
    subprocess.run(
        [sys.executable, "-m", "app.entrypoints.cli.main", "admin", "migrate"],
        check=True,
        cwd=repo_root,
        env=env,
    )
