"""Shared fixtures for read execution integration tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from math import sqrt

import pytest
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from app.core.entities.memory import MemoryKind, MemoryScope
from app.core.interfaces.retrieval import IVectorSearch
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


class _StubVectorSearch(IVectorSearch):
    """Deterministic query-vector provider for semantic execution tests."""

    def __init__(self, vectors_by_query: dict[str, list[float]]) -> None:
        """Store the query-to-vector mapping used by a semantic test."""

        self._vectors_by_query = vectors_by_query

    def embed_query(self, text: str) -> list[float]:
        """Return the preconfigured query vector for the provided text."""

        if text not in self._vectors_by_query:
            raise KeyError(f"No stub query vector configured for: {text}")
        return list(self._vectors_by_query[text])


class DeterministicSemanticRetrievalRepo:
    """Test-only semantic retrieval repo with deterministic vector scoring."""

    def __init__(
        self,
        session,
        *,
        vector_search: IVectorSearch,
        active_query_text: str,
        direct_threshold: float = 0.75,
        neighbor_threshold: float = 0.000001,
    ) -> None:
        """Bind the active session and query-vector provider for one read call."""

        self._session = session
        self._vector_search = vector_search
        self._active_query_text = active_query_text
        self._direct_threshold = direct_threshold
        self._neighbor_threshold = neighbor_threshold

    def query_semantic(
        self,
        *,
        repo_id: str,
        include_global: bool,
        query_vector,
        kinds,
        limit: int,
    ) -> list[dict[str, object]]:
        """Return direct semantic seeds ranked by deterministic cosine similarity."""

        active_query_vector = list(query_vector) or list(self._vector_search.embed_query(self._active_query_text))
        scored: list[dict[str, object]] = []
        for row in self._visible_embedding_rows(repo_id=repo_id, include_global=include_global, kinds=kinds):
            score = _cosine_similarity(active_query_vector, row["vector"])
            if score < self._direct_threshold:
                continue
            scored.append({"memory_id": row["memory_id"], "score": score})
        scored.sort(key=lambda item: (-float(item["score"]), str(item["memory_id"])))
        return scored[:limit]

    def list_semantic_neighbors(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        """Return semantic neighbors for an anchor memory using the same deterministic scoring."""

        visible_rows = self._visible_embedding_rows(repo_id=repo_id, include_global=include_global, kinds=kinds)
        anchor_vector = next(
            (row["vector"] for row in visible_rows if row["memory_id"] == anchor_memory_id),
            None,
        )
        if anchor_vector is None:
            return []

        scored: list[dict[str, object]] = []
        for row in visible_rows:
            if row["memory_id"] == anchor_memory_id:
                continue
            score = _cosine_similarity(anchor_vector, row["vector"])
            if score < self._neighbor_threshold:
                continue
            scored.append({"memory_id": row["memory_id"], "score": score})
        scored.sort(key=lambda item: (-float(item["score"]), str(item["memory_id"])))
        if limit is None:
            return scored
        return scored[:limit]

    def _visible_embedding_rows(self, *, repo_id: str, include_global: bool, kinds) -> list[dict[str, object]]:
        """Load visible embedded memories eligible for semantic retrieval."""

        scope_values = ["repo", "global"] if include_global else ["repo"]
        stmt = (
            select(
                memories.c.id.label("memory_id"),
                memory_embeddings.c.vector,
            )
            .select_from(memories.join(memory_embeddings, memory_embeddings.c.memory_id == memories.c.id))
            .where(
                memories.c.repo_id == repo_id,
                memories.c.archived.is_(False),
                memories.c.scope.in_(scope_values),
            )
        )
        if kinds:
            stmt = stmt.where(memories.c.kind.in_(list(kinds)))
        rows = self._session.execute(stmt).mappings().all()
        return [
            {
                "memory_id": str(row["memory_id"]),
                "vector": [float(value) for value in row["vector"]],
            }
            for row in rows
        ]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute a deterministic cosine similarity for semantic test vectors."""

    if len(left) != len(right):
        return 0.0
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    return dot / (left_norm * right_norm)


@pytest.fixture
def stub_vector_search() -> Callable[[dict[str, list[float]]], IVectorSearch]:
    """Build deterministic query-vector providers for semantic execution tests."""

    def _build(vectors_by_query: dict[str, list[float]]) -> IVectorSearch:
        return _StubVectorSearch(vectors_by_query)

    return _build


@pytest.fixture
def semantic_retrieval_override_factory() -> Callable[..., DeterministicSemanticRetrievalRepo]:
    """Build deterministic semantic retrieval repos bound to a live session."""

    def _build(
        *,
        session,
        vector_search: IVectorSearch,
        active_query_text: str,
        direct_threshold: float = 0.75,
        neighbor_threshold: float = 0.000001,
    ) -> DeterministicSemanticRetrievalRepo:
        return DeterministicSemanticRetrievalRepo(
            session,
            vector_search=vector_search,
            active_query_text=active_query_text,
            direct_threshold=direct_threshold,
            neighbor_threshold=neighbor_threshold,
        )

    return _build
