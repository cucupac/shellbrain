"""Shared PostgreSQL integration fixtures for operation execution tests."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import Selectable

from app.core.entities.episodes import Episode, EpisodeEvent, EpisodeEventSource, EpisodeStatus
from app.core.entities.memory import Memory, MemoryKind, MemoryScope
from app.core.interfaces.embeddings import IEmbeddingProvider
from app.periphery.db.engine import get_engine
from app.periphery.db.models.registry import target_metadata
from app.periphery.db.session import get_session_factory
from app.periphery.db.uow import PostgresUnitOfWork


class _StubEmbeddingProvider(IEmbeddingProvider):
    """Deterministic embedding provider for integration tests."""

    def embed(self, text: str) -> list[float]:
        length = float(len(text) % 7) / 10.0
        return [length, length + 0.1, length + 0.2, length + 0.3]


@pytest.fixture(scope="session")
def db_dsn() -> str:
    """Resolve integration database DSN from environment."""

    dsn = os.getenv("MEMORY_DB_DSN_TEST")
    if not dsn:
        pytest.skip("Set MEMORY_DB_DSN_TEST to run PostgreSQL integration tests.")
    return dsn


@pytest.fixture(scope="session")
def integration_engine(db_dsn: str) -> Iterator[Engine]:
    """Create and migrate integration engine once per test session."""

    engine = get_engine(db_dsn)
    _run_alembic_upgrade(db_dsn)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def integration_session_factory(integration_engine: Engine) -> sessionmaker:
    """Build reusable session factory for integration tests."""

    return get_session_factory(integration_engine)


@pytest.fixture(autouse=True)
def clear_database(integration_engine: Engine) -> Iterator[None]:
    """Truncate all tables between integration tests."""

    table_names = [table.name for table in reversed(target_metadata.sorted_tables)]
    if table_names:
        joined = ", ".join(table_names)
        with integration_engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE;"))
    yield


@pytest.fixture
def uow_factory(integration_session_factory: sessionmaker) -> Callable[[], PostgresUnitOfWork]:
    """Provide unit-of-work factory bound to integration database."""

    def _factory() -> PostgresUnitOfWork:
        return PostgresUnitOfWork(integration_session_factory)

    return _factory


@pytest.fixture
def stub_embedding_provider() -> IEmbeddingProvider:
    """Provide deterministic embedding provider for execution tests."""

    return _StubEmbeddingProvider()


@pytest.fixture
def seed_memory(uow_factory: Callable[[], PostgresUnitOfWork]) -> Callable[..., Memory]:
    """Provide helper for seeding memory rows into integration database."""

    def _seed(
        *,
        memory_id: str,
        repo_id: str,
        scope: MemoryScope,
        kind: MemoryKind,
        text_value: str,
    ) -> Memory:
        memory = Memory(
            id=memory_id,
            repo_id=repo_id,
            scope=scope,
            kind=kind,
            text=text_value,
        )
        with uow_factory() as uow:
            uow.memories.create(memory)
        return memory

    return _seed


@pytest.fixture
def seed_episode(uow_factory: Callable[[], PostgresUnitOfWork]) -> Callable[..., Episode]:
    """Provide helper for seeding episode rows into integration database."""

    def _seed(
        *,
        episode_id: str,
        repo_id: str,
        host_app: str,
        thread_id: str,
        status: EpisodeStatus = EpisodeStatus.ACTIVE,
        started_at: datetime | None = None,
    ) -> Episode:
        episode = Episode(
            id=episode_id,
            repo_id=repo_id,
            host_app=host_app,
            thread_id=thread_id,
            status=status,
            started_at=started_at or datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        with uow_factory() as uow:
            uow.episodes.create_episode(episode)
        return episode

    return _seed


@pytest.fixture
def seed_episode_event(uow_factory: Callable[[], PostgresUnitOfWork]) -> Callable[..., EpisodeEvent]:
    """Provide helper for seeding episode-event rows into integration database."""

    def _seed(
        *,
        event_id: str,
        episode_id: str,
        seq: int,
        source: EpisodeEventSource | str = EpisodeEventSource.USER,
        host_event_key: str | None = None,
        content: str = '{"content_text":"evidence"}',
        created_at: datetime | None = None,
    ) -> EpisodeEvent:
        normalized_source = source if isinstance(source, EpisodeEventSource) else EpisodeEventSource(source)
        event = EpisodeEvent(
            id=event_id,
            episode_id=episode_id,
            seq=seq,
            host_event_key=host_event_key or event_id,
            source=normalized_source,
            content=content,
            created_at=created_at or datetime.now(timezone.utc),
        )
        with uow_factory() as uow:
            uow.episodes.append_event(event)
        return event

    return _seed


@pytest.fixture
def seed_default_evidence_events(
    seed_episode: Callable[..., Episode],
    seed_episode_event: Callable[..., EpisodeEvent],
) -> Callable[..., dict[str, EpisodeEvent]]:
    """Provide helper for seeding canonical evidence events used by create/update integration tests."""

    def _seed(*, repo_id: str = "repo-a") -> dict[str, EpisodeEvent]:
        episode = seed_episode(
            episode_id=f"{repo_id}-episode-evidence",
            repo_id=repo_id,
            host_app="codex",
            thread_id=f"codex:{repo_id}-episode-evidence",
        )
        seeded: dict[str, EpisodeEvent] = {}
        for seq, event_id in enumerate(("session://1", "session://2", "integration://evidence/1"), start=1):
            seeded[event_id] = seed_episode_event(
                event_id=event_id,
                episode_id=episode.id,
                seq=seq,
                source=EpisodeEventSource.USER,
                content=f'{{"content_text":"{event_id}"}}',
            )
        return seeded

    return _seed


@pytest.fixture
def count_rows(integration_engine: Engine) -> Callable[[str], int]:
    """Provide helper for counting rows in a table."""

    def _count(table_name: str) -> int:
        with integration_engine.connect() as conn:
            return int(conn.execute(text(f"SELECT COUNT(*) FROM {table_name};")).scalar_one())

    return _count


@pytest.fixture
def fetch_rows(integration_engine: Engine) -> Callable[[Selectable, object], list[dict[str, object]]]:
    """Provide helper for selecting rows from a SQLAlchemy table with optional where clauses."""

    def _fetch(table: Selectable, *conditions: object) -> list[dict[str, object]]:
        stmt = select(table)
        if conditions:
            stmt = stmt.where(*conditions)
        with integration_engine.connect() as conn:
            return [dict(row) for row in conn.execute(stmt).mappings().all()]

    return _fetch


def _run_alembic_upgrade(dsn: str) -> None:
    """Run alembic upgrade head against integration database."""

    repo_root = _find_repo_root()
    env = dict(os.environ)
    env["MEMORY_DB_DSN"] = dsn
    subprocess.run(
        ["alembic", "upgrade", "head"],
        check=True,
        cwd=repo_root,
        env=env,
    )


def _find_repo_root() -> Path:
    """Resolve repository root by walking upward until alembic.ini is found."""

    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "alembic.ini").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not resolve repository root from execution test fixtures.")
