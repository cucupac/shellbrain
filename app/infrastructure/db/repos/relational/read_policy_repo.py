"""This module defines SQL-backed read-path visibility and explicit expansion queries."""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import or_, select, union_all

from app.core.interfaces.repos import IReadPolicyRepo
from app.infrastructure.db.models.associations import association_edges
from app.infrastructure.db.models.experiences import fact_updates, problem_attempts
from app.infrastructure.db.models.memories import memories


class ReadPolicyRepo(IReadPolicyRepo):
    """This class provides visibility-gated read-path expansion queries."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for read-path queries."""

        self._session = session

    def list_problem_attempt_rows(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
    ) -> Sequence[dict[str, Any]]:
        """Return problem-attempt rows touching an anchor plus visible participants."""

        rows = (
            self._session.execute(
                select(problem_attempts.c.problem_id, problem_attempts.c.attempt_id).where(
                    or_(
                        problem_attempts.c.problem_id == anchor_memory_id,
                        problem_attempts.c.attempt_id == anchor_memory_id,
                    )
                )
            )
            .mappings()
            .all()
        )
        return [
            {
                "problem_id": str(row["problem_id"]),
                "attempt_id": str(row["attempt_id"]),
                "visible_memory_ids": tuple(
                    sorted(
                        self._visible_memory_ids(
                            repo_id=repo_id,
                            include_global=include_global,
                            kinds=kinds,
                            memory_ids=(str(row["problem_id"]), str(row["attempt_id"])),
                        )
                    )
                ),
            }
            for row in rows
        ]

    def list_fact_update_rows(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
    ) -> Sequence[dict[str, Any]]:
        """Return fact-update rows touching an anchor plus visible participants."""

        rows = (
            self._session.execute(
                select(fact_updates.c.old_fact_id, fact_updates.c.change_id, fact_updates.c.new_fact_id).where(
                    or_(
                        fact_updates.c.old_fact_id == anchor_memory_id,
                        fact_updates.c.change_id == anchor_memory_id,
                        fact_updates.c.new_fact_id == anchor_memory_id,
                    )
                )
            )
            .mappings()
            .all()
        )
        return [
            {
                "old_fact_id": str(row["old_fact_id"]),
                "change_id": str(row["change_id"]),
                "new_fact_id": str(row["new_fact_id"]),
                "visible_memory_ids": tuple(
                    sorted(
                        self._visible_memory_ids(
                            repo_id=repo_id,
                            include_global=include_global,
                            kinds=kinds,
                            memory_ids=(
                                str(row["old_fact_id"]),
                                str(row["change_id"]),
                                str(row["new_fact_id"]),
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
            .select_from(association_edges.join(memories, memories.c.id == association_edges.c.to_memory_id))
            .where(
                association_edges.c.repo_id == repo_id,
                association_edges.c.from_memory_id == anchor_memory_id,
                association_edges.c.state != "deprecated",
                *self._visibility_filters(repo_id=repo_id, include_global=include_global, kinds=kinds),
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
            .select_from(association_edges.join(memories, memories.c.id == association_edges.c.from_memory_id))
            .where(
                association_edges.c.repo_id == repo_id,
                association_edges.c.to_memory_id == anchor_memory_id,
                association_edges.c.state != "deprecated",
                *self._visibility_filters(repo_id=repo_id, include_global=include_global, kinds=kinds),
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

        unique_memory_ids = tuple(dict.fromkeys(str(memory_id) for memory_id in memory_ids))
        if not unique_memory_ids:
            return set()
        rows = self._session.execute(
            select(memories.c.id).where(
                memories.c.id.in_(unique_memory_ids),
                *self._visibility_filters(repo_id=repo_id, include_global=include_global, kinds=kinds),
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
            memories.c.archived.is_(False),
            memories.c.scope.in_(scope_values),
        ]
        if kinds:
            filters.append(memories.c.kind.in_(list(kinds)))
        return filters
