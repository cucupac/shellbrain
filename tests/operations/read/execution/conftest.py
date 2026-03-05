"""Shared fixtures for read execution integration tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

import pytest
from sqlalchemy import insert
from sqlalchemy.engine import Engine

from app.core.entities.memory import MemoryKind, MemoryScope
from app.periphery.db.models.associations import association_edges
from app.periphery.db.models.experiences import fact_updates, problem_attempts
from app.periphery.db.models.memories import memories, memory_embeddings

from tests.operations._shared.integration_db_fixtures import *  # noqa: F401,F403


_BASE_TS = datetime(2024, 1, 1, tzinfo=timezone.utc)
_TABLES_FOR_MUTATION_CHECK = (
    "memories",
    "memory_embeddings",
    "memory_evidence",
    "problem_attempts",
    "fact_updates",
    "association_edges",
    "association_observations",
    "association_edge_evidence",
    "utility_observations",
    "evidence_refs",
)


@pytest.fixture
def seed_read_memory(integration_engine: Engine) -> Callable[..., None]:
    """Insert deterministic memory rows used by read execution tests."""

    def _seed(
        *,
        memory_id: str,
        repo_id: str,
        scope: MemoryScope | str,
        kind: MemoryKind | str,
        text_value: str,
        archived: bool = False,
        confidence: float | None = 0.7,
        created_at: datetime | None = None,
    ) -> None:
        scope_value = scope.value if isinstance(scope, MemoryScope) else scope
        kind_value = kind.value if isinstance(kind, MemoryKind) else kind
        ts = created_at or _BASE_TS
        with integration_engine.begin() as conn:
            conn.execute(
                insert(memories).values(
                    id=memory_id,
                    repo_id=repo_id,
                    scope=scope_value,
                    kind=kind_value,
                    text=text_value,
                    create_confidence=confidence,
                    created_at=ts,
                    archived=archived,
                )
            )

    return _seed


@pytest.fixture
def seed_read_embedding(integration_engine: Engine) -> Callable[..., None]:
    """Insert deterministic embedding rows for semantic retrieval scenarios."""

    def _seed(
        *,
        memory_id: str,
        model: str = "stub-v1",
        vector: list[float] | None = None,
        created_at: datetime | None = None,
    ) -> None:
        embedding = vector or [0.1, 0.2, 0.3, 0.4]
        ts = created_at or _BASE_TS
        with integration_engine.begin() as conn:
            conn.execute(
                insert(memory_embeddings).values(
                    memory_id=memory_id,
                    model=model,
                    dim=len(embedding),
                    vector=embedding,
                    created_at=ts,
                )
            )

    return _seed


@pytest.fixture
def seed_problem_attempt_link(integration_engine: Engine) -> Callable[..., None]:
    """Insert deterministic problem-attempt links for explicit expansion scenarios."""

    def _seed(
        *,
        problem_id: str,
        attempt_id: str,
        role: str,
        created_at: datetime | None = None,
    ) -> None:
        ts = created_at or _BASE_TS
        with integration_engine.begin() as conn:
            conn.execute(
                insert(problem_attempts).values(
                    problem_id=problem_id,
                    attempt_id=attempt_id,
                    role=role,
                    created_at=ts,
                )
            )

    return _seed


@pytest.fixture
def seed_fact_update_link(integration_engine: Engine) -> Callable[..., None]:
    """Insert deterministic fact-update links for explicit expansion scenarios."""

    def _seed(
        *,
        link_id: str,
        old_fact_id: str,
        change_id: str,
        new_fact_id: str,
        created_at: datetime | None = None,
    ) -> None:
        ts = created_at or _BASE_TS
        with integration_engine.begin() as conn:
            conn.execute(
                insert(fact_updates).values(
                    id=link_id,
                    old_fact_id=old_fact_id,
                    change_id=change_id,
                    new_fact_id=new_fact_id,
                    created_at=ts,
                )
            )

    return _seed


@pytest.fixture
def seed_association_edge(integration_engine: Engine) -> Callable[..., None]:
    """Insert deterministic association edges for explicit expansion scenarios."""

    def _seed(
        *,
        edge_id: str,
        repo_id: str,
        from_memory_id: str,
        to_memory_id: str,
        relation_type: str,
        strength: float,
        source_mode: str = "agent",
        state: str = "tentative",
        obs_count: int = 0,
        positive_obs: int = 0,
        negative_obs: int = 0,
        salience_sum: float = 0.0,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        created_ts = created_at or _BASE_TS
        updated_ts = updated_at or created_ts
        with integration_engine.begin() as conn:
            conn.execute(
                insert(association_edges).values(
                    id=edge_id,
                    repo_id=repo_id,
                    from_memory_id=from_memory_id,
                    to_memory_id=to_memory_id,
                    relation_type=relation_type,
                    source_mode=source_mode,
                    state=state,
                    strength=strength,
                    obs_count=obs_count,
                    positive_obs=positive_obs,
                    negative_obs=negative_obs,
                    salience_sum=salience_sum,
                    created_at=created_ts,
                    updated_at=updated_ts,
                )
            )

    return _seed


@pytest.fixture
def snapshot_row_counts(count_rows: Callable[[str], int]) -> Callable[[], dict[str, int]]:
    """Capture row counts for tracked tables to assert retrieval-only behavior."""

    def _snapshot() -> dict[str, int]:
        return {table_name: count_rows(table_name) for table_name in _TABLES_FOR_MUTATION_CHECK}

    return _snapshot
