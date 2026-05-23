"""This module defines SQL-backed read-path visibility and explicit expansion queries."""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import or_, select, union_all

from app.core.policies.retrieval.ontology_semantics import POSITIVE_LIFECYCLE_STATUSES
from app.core.ports.db.retrieval_repositories import IReadPolicyRepo
from app.infrastructure.db.runtime.models.associations import association_edges
from app.infrastructure.db.runtime.models.experiences import structural_memory_relations
from app.infrastructure.db.runtime.models.memories import memories


class ReadPolicyRepo(IReadPolicyRepo):
    """This class provides visibility-gated read-path expansion queries."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for read-path queries."""

        self._session = session

    def list_structural_memory_relation_rows(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
        predicates: Sequence[str],
    ) -> Sequence[dict[str, Any]]:
        """Return active structural relation rows touching an anchor."""

        rows = (
            self._session.execute(
                select(
                    structural_memory_relations.c.subject_memory_id,
                    structural_memory_relations.c.predicate,
                    structural_memory_relations.c.object_memory_id,
                ).where(
                    structural_memory_relations.c.repo_id == repo_id,
                    structural_memory_relations.c.predicate.in_(list(predicates)),
                    structural_memory_relations.c.status.in_(
                        list(POSITIVE_LIFECYCLE_STATUSES)
                    ),
                    or_(
                        structural_memory_relations.c.subject_memory_id
                        == anchor_memory_id,
                        structural_memory_relations.c.object_memory_id
                        == anchor_memory_id,
                    ),
                )
            )
            .mappings()
            .all()
        )
        return [
            {
                "subject_memory_id": str(row["subject_memory_id"]),
                "predicate": str(row["predicate"]),
                "object_memory_id": str(row["object_memory_id"]),
                "visible_memory_ids": tuple(
                    sorted(
                        self._visible_memory_ids(
                            repo_id=repo_id,
                            include_global=include_global,
                            kinds=kinds,
                            memory_ids=(
                                str(row["subject_memory_id"]),
                                str(row["object_memory_id"]),
                            ),
                        )
                    )
                ),
            }
            for row in rows
        ]

    def list_association_edge_rows(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
    ) -> Sequence[dict[str, Any]]:
        """Return visible active association edge rows touching one anchor."""

        from_stmt = (
            select(
                association_edges.c.from_memory_id,
                association_edges.c.to_memory_id.label("memory_id"),
                association_edges.c.to_memory_id,
                association_edges.c.relation_type,
                association_edges.c.strength,
            )
            .select_from(
                association_edges.join(
                    memories, memories.c.id == association_edges.c.to_memory_id
                )
            )
            .where(
                association_edges.c.repo_id == repo_id,
                association_edges.c.from_memory_id == anchor_memory_id,
                association_edges.c.state != "deprecated",
                *self._visibility_filters(
                    repo_id=repo_id, include_global=include_global, kinds=kinds
                ),
            )
        )
        to_stmt = (
            select(
                association_edges.c.from_memory_id,
                association_edges.c.from_memory_id.label("memory_id"),
                association_edges.c.to_memory_id,
                association_edges.c.relation_type,
                association_edges.c.strength,
            )
            .select_from(
                association_edges.join(
                    memories, memories.c.id == association_edges.c.from_memory_id
                )
            )
            .where(
                association_edges.c.repo_id == repo_id,
                association_edges.c.to_memory_id == anchor_memory_id,
                association_edges.c.state != "deprecated",
                *self._visibility_filters(
                    repo_id=repo_id, include_global=include_global, kinds=kinds
                ),
            )
        )
        union_stmt = union_all(from_stmt, to_stmt).subquery()
        stmt = (
            select(
                union_stmt.c.from_memory_id,
                union_stmt.c.to_memory_id,
                union_stmt.c.memory_id,
                union_stmt.c.relation_type,
                union_stmt.c.strength,
            )
            .where(union_stmt.c.memory_id != anchor_memory_id)
            .order_by(union_stmt.c.memory_id.asc(), union_stmt.c.relation_type.asc())
        )
        return list(self._session.execute(stmt).mappings().all())

    def _visible_memory_ids(
        self,
        *,
        repo_id: str,
        include_global: bool,
        kinds: Sequence[str] | None,
        memory_ids: Sequence[str],
    ) -> set[str]:
        """Return the visible subset of memory ids."""

        unique_memory_ids = tuple(
            dict.fromkeys(str(memory_id) for memory_id in memory_ids)
        )
        if not unique_memory_ids:
            return set()
        rows = self._session.execute(
            select(memories.c.id).where(
                memories.c.id.in_(unique_memory_ids),
                *self._visibility_filters(
                    repo_id=repo_id, include_global=include_global, kinds=kinds
                ),
            )
        )
        return {str(row[0]) for row in rows}

    def _visibility_filters(
        self,
        *,
        repo_id: str,
        include_global: bool,
        kinds: Sequence[str] | None,
    ) -> list[Any]:
        """Build the visibility filters used by read-path queries."""

        scope_values = ["repo", "global"] if include_global else ["repo"]
        filters: list[Any] = [
            memories.c.repo_id == repo_id,
            memories.c.status.in_(list(POSITIVE_LIFECYCLE_STATUSES)),
            memories.c.scope.in_(scope_values),
        ]
        if kinds:
            filters.append(memories.c.kind.in_(list(kinds)))
        return filters
