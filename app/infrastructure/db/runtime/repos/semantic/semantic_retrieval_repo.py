"""This module defines semantic-lane retrieval operations over stored shellbrain embeddings."""

from typing import Any, Sequence

from sqlalchemy import case, desc, or_, select

from app.core.ports.db.retrieval_repositories import ISemanticRetrievalRepo
from app.core.policies.retrieval.ontology_semantics import (
    LIFECYCLE_RETRIEVAL_MULTIPLIERS,
    MAYBE_STALE_STATUS,
    POSITIVE_LIFECYCLE_STATUSES,
    STALE_STATUS,
)
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
        if _is_zero_vector(query_values):
            return []
        self._raise_on_incompatible_visible_embedding(
            repo_id=repo_id,
            include_global=include_global,
            kinds=kinds,
            expected_dim=len(query_values),
            expected_model=query_model,
            reference_label="query embedding",
        )

        distance = memory_embeddings.c.vector.cosine_distance(query_values)
        score = ((1.0 - distance) * _memory_status_multiplier()).label("score")
        stmt = (
            select(
                memories.c.id.label("memory_id"),
                score,
            )
            .select_from(
                memories.join(
                    memory_embeddings, memory_embeddings.c.memory_id == memories.c.id
                )
            )
            .where(
                *self._visibility_filters(
                    repo_id=repo_id,
                    include_global=include_global,
                    kinds=kinds,
                ),
                memory_embeddings.c.dim == len(query_values),
            )
            .order_by(desc(score), memories.c.id.asc())
            .limit(limit)
        )
        if query_model is not None:
            stmt = stmt.where(memory_embeddings.c.model == query_model)

        return [
            {"memory_id": str(row["memory_id"]), "score": float(row["score"])}
            for row in self._session.execute(stmt).mappings().all()
            if _is_positive_score(row["score"])
        ]

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

        anchor_row = self._visible_anchor_embedding_row(
            repo_id=repo_id,
            include_global=include_global,
            kinds=kinds,
            anchor_memory_id=anchor_memory_id,
        )
        if anchor_row is None:
            return []
        _validate_embedding_row(anchor_row)
        if _is_zero_vector(anchor_row["vector"]):
            return []

        self._raise_on_incompatible_visible_embedding(
            repo_id=repo_id,
            include_global=include_global,
            kinds=kinds,
            expected_dim=int(anchor_row["dim"]),
            expected_model=str(anchor_row["model"]),
            reference_label=f"anchor embedding {anchor_memory_id}",
        )

        distance = memory_embeddings.c.vector.cosine_distance(anchor_row["vector"])
        score = ((1.0 - distance) * _memory_status_multiplier()).label("score")
        stmt = (
            select(
                memories.c.id.label("memory_id"),
                score,
            )
            .select_from(
                memories.join(
                    memory_embeddings, memory_embeddings.c.memory_id == memories.c.id
                )
            )
            .where(
                *self._visibility_filters(
                    repo_id=repo_id,
                    include_global=include_global,
                    kinds=kinds,
                ),
                memories.c.id != anchor_memory_id,
                memory_embeddings.c.dim == int(anchor_row["dim"]),
                memory_embeddings.c.model == str(anchor_row["model"]),
            )
            .order_by(desc(score), memories.c.id.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        return [
            {"memory_id": str(row["memory_id"]), "score": float(row["score"])}
            for row in self._session.execute(stmt).mappings().all()
            if _is_positive_score(row["score"])
        ]

    def _visible_anchor_embedding_row(
        self,
        *,
        repo_id: str,
        include_global: bool,
        kinds: Sequence[str] | None,
        anchor_memory_id: str,
    ) -> dict[str, Any] | None:
        """Load the one visible anchor embedding used for semantic expansion."""

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
                *self._visibility_filters(
                    repo_id=repo_id,
                    include_global=include_global,
                    kinds=kinds,
                ),
                memories.c.id == anchor_memory_id,
            )
            .limit(1)
        )
        row = self._session.execute(stmt).mappings().first()
        if row is None:
            return None
        return {
            "memory_id": str(row["memory_id"]),
            "model": str(row["model"]),
            "dim": int(row["dim"]),
            "vector": [float(value) for value in row["vector"]],
        }

    def _raise_on_incompatible_visible_embedding(
        self,
        *,
        repo_id: str,
        include_global: bool,
        kinds: Sequence[str] | None,
        expected_dim: int,
        expected_model: str | None,
        reference_label: str,
    ) -> None:
        """Fail before vector search when visible embeddings cannot be compared."""

        mismatch_predicate = memory_embeddings.c.dim != expected_dim
        if expected_model is not None:
            mismatch_predicate = or_(
                mismatch_predicate, memory_embeddings.c.model != expected_model
            )
        stmt = (
            select(
                memories.c.id.label("memory_id"),
                memory_embeddings.c.model,
                memory_embeddings.c.dim,
            )
            .select_from(
                memories.join(
                    memory_embeddings, memory_embeddings.c.memory_id == memories.c.id
                )
            )
            .where(
                *self._visibility_filters(
                    repo_id=repo_id,
                    include_global=include_global,
                    kinds=kinds,
                ),
                mismatch_predicate,
            )
            .order_by(memories.c.id.asc())
            .limit(1)
        )
        row = self._session.execute(stmt).mappings().first()
        if row is None:
            return
        _validate_embedding_space(
            {
                "memory_id": str(row["memory_id"]),
                "model": str(row["model"]),
                "dim": int(row["dim"]),
                "vector": [],
            },
            expected_dim=expected_dim,
            expected_model=expected_model,
            reference_label=reference_label,
        )

    def _visibility_filters(
        self,
        *,
        repo_id: str,
        include_global: bool,
        kinds: Sequence[str] | None,
    ) -> list[Any]:
        """Build the visibility filters used by semantic retrieval queries."""

        scope_values = ["repo", "global"] if include_global else ["repo"]
        filters: list[Any] = [
            memories.c.repo_id == repo_id,
            memories.c.status.in_(list(POSITIVE_LIFECYCLE_STATUSES)),
            memories.c.scope.in_(scope_values),
        ]
        if kinds:
            filters.append(memories.c.kind.in_(list(kinds)))
        return filters


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


def _is_zero_vector(vector: Sequence[float]) -> bool:
    """Return whether a vector has zero magnitude."""

    return not any(float(value) != 0.0 for value in vector)


def _is_positive_score(value: Any) -> bool:
    """Return whether one database similarity score is usable."""

    if value is None:
        return False
    score = float(value)
    return score > 0.0 and score == score


def _memory_status_multiplier():
    """Return SQL expression for lifecycle-aware memory retrieval strength."""

    return case(
        (
            memories.c.status == MAYBE_STALE_STATUS,
            LIFECYCLE_RETRIEVAL_MULTIPLIERS[MAYBE_STALE_STATUS],
        ),
        (
            memories.c.status == STALE_STATUS,
            LIFECYCLE_RETRIEVAL_MULTIPLIERS[STALE_STATUS],
        ),
        else_=1.0,
    )
