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
        query_model: str | None = None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns semantic candidates and similarity scores."""

        if not query_vector:
            return []

        query_values = [float(value) for value in query_vector]
        scored: list[dict[str, Any]] = []
        for row in self._visible_embedding_rows(
            repo_id=repo_id, include_global=include_global, kinds=kinds
        ):
            _validate_embedding_row(row)
            _validate_embedding_space(
                row,
                expected_dim=len(query_values),
                expected_model=query_model,
                reference_label="query embedding",
            )
            score = _cosine_similarity(query_values, row["vector"])
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
        anchor_row = next(
            row for row in visible_rows if row["memory_id"] == anchor_memory_id
        )
        _validate_embedding_row(anchor_row)

        scored: list[dict[str, Any]] = []
        for row in visible_rows:
            if row["memory_id"] == anchor_memory_id:
                continue
            _validate_embedding_row(row)
            _validate_embedding_space(
                row,
                expected_dim=int(anchor_row["dim"]),
                expected_model=str(anchor_row["model"]),
                reference_label=f"anchor embedding {anchor_memory_id}",
            )
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
                memory_embeddings.c.model,
                memory_embeddings.c.dim,
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
                "model": str(row["model"]),
                "dim": int(row["dim"]),
                "vector": [float(value) for value in row["vector"]],
            }
            for row in rows
        ]


def _validate_embedding_row(row: dict[str, Any]) -> None:
    """Validate one persisted embedding before it can participate in scoring."""

    vector_length = len(row["vector"])
    declared_dim = int(row["dim"])
    if vector_length != declared_dim:
        raise ValueError(
            "Stored semantic embedding dimension mismatch for "
            f"{row['memory_id']}: dim={declared_dim}, vector_length={vector_length}"
        )


def _validate_embedding_space(
    row: dict[str, Any],
    *,
    expected_dim: int,
    expected_model: str | None,
    reference_label: str,
) -> None:
    """Ensure one candidate embedding is comparable with the reference embedding."""

    row_dim = int(row["dim"])
    if row_dim != expected_dim:
        raise ValueError(
            "Semantic embedding dimension mismatch for "
            f"{row['memory_id']}: {reference_label} dim={expected_dim}, "
            f"stored dim={row_dim}"
        )
    if expected_model is not None and str(row["model"]) != expected_model:
        raise ValueError(
            "Semantic embedding model mismatch for "
            f"{row['memory_id']}: {reference_label} model={expected_model}, "
            f"stored model={row['model']}"
        )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity for semantic retrieval ranking and gating."""

    if len(left) != len(right):
        raise ValueError(
            "Cosine similarity requires vectors with the same dimension: "
            f"left={len(left)}, right={len(right)}"
        )
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(
        left_value * right_value
        for left_value, right_value in zip(left, right, strict=True)
    )
    return dot / (left_norm * right_norm)
