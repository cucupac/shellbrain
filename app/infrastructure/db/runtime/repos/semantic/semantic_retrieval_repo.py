"""This module defines semantic-lane retrieval operations over stored shellbrain embeddings."""

from math import sqrt
from typing import Any, Sequence

from sqlalchemy import select

from app.core.ports.db.retrieval_repositories import ISemanticRetrievalRepo
from app.infrastructure.db.runtime.models.memories import memories, memory_embeddings


class SemanticRetrievalRepo(ISemanticRetrievalRepo):
    """This class provides semantic retrieval candidates from embedding similarity."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for semantic retrieval operations."""

        self._session = session

    def query_semantic(
        self,
        *,
        repo_id: str,
        include_global: bool,
        query_vector: Sequence[float],
        kinds: Sequence[str] | None,
        limit: int,
    ) -> Sequence[dict[str, Any]]:
        """This method returns semantic candidates and similarity scores."""

        if not query_vector:
            return []

        scored: list[dict[str, Any]] = []
        for row in self._visible_embedding_rows(
            repo_id=repo_id, include_global=include_global, kinds=kinds
        ):
            score = _cosine_similarity(list(query_vector), row["vector"])
            if score <= 0.0:
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
        kinds: Sequence[str] | None,
        limit: int | None = None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns implicit semantic neighbors for one anchor memory."""

        visible_rows = self._visible_embedding_rows(
            repo_id=repo_id, include_global=include_global, kinds=kinds
        )
        anchor_vector = next(
            (
                row["vector"]
                for row in visible_rows
                if row["memory_id"] == anchor_memory_id
            ),
            None,
        )
        if anchor_vector is None:
            return []

        scored: list[dict[str, Any]] = []
        for row in visible_rows:
            if row["memory_id"] == anchor_memory_id:
                continue
            score = _cosine_similarity(anchor_vector, row["vector"])
            if score <= 0.0:
                continue
            scored.append({"memory_id": row["memory_id"], "score": score})
        scored.sort(key=lambda item: (-float(item["score"]), str(item["memory_id"])))
        if limit is None:
            return scored
        return scored[:limit]

    def _visible_embedding_rows(
        self, *, repo_id: str, include_global: bool, kinds: Sequence[str] | None
    ) -> list[dict[str, Any]]:
        """Load visible embedded memories eligible for semantic retrieval."""

        scope_values = ["repo", "global"] if include_global else ["repo"]
        stmt = (
            select(
                memories.c.id.label("memory_id"),
                memory_embeddings.c.vector,
            )
            .select_from(
                memories.join(
                    memory_embeddings, memory_embeddings.c.memory_id == memories.c.id
                )
            )
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
    """Compute cosine similarity for semantic retrieval ranking and gating."""

    if len(left) != len(right):
        return 0.0
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=True)
    )
    return dot / (left_norm * right_norm)
