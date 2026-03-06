"""This module defines SQL-backed read-path visibility and explicit expansion queries."""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import func, literal, or_, select, union_all

from app.core.interfaces.repos import IReadPolicyRepo
from app.periphery.db.models.associations import association_edges
from app.periphery.db.models.experiences import fact_updates, problem_attempts
from app.periphery.db.models.memories import memories


class ReadPolicyRepo(IReadPolicyRepo):
    """This class provides visibility-gated read-path expansion queries."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for read-path queries."""

        self._session = session

    def list_problem_attempt_neighbors(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns visible problem-attempt neighbors for an anchor memory."""

        attempt_stmt = (
            select(problem_attempts.c.attempt_id.label("memory_id"), literal("problem_attempt").label("expansion_type"))
            .select_from(problem_attempts.join(memories, memories.c.id == problem_attempts.c.attempt_id))
            .where(
                problem_attempts.c.problem_id == anchor_memory_id,
                *self._visibility_filters(repo_id=repo_id, include_global=include_global, kinds=kinds),
            )
        )
        problem_stmt = (
            select(problem_attempts.c.problem_id.label("memory_id"), literal("problem_attempt").label("expansion_type"))
            .select_from(problem_attempts.join(memories, memories.c.id == problem_attempts.c.problem_id))
            .where(
                problem_attempts.c.attempt_id == anchor_memory_id,
                *self._visibility_filters(repo_id=repo_id, include_global=include_global, kinds=kinds),
            )
        )
        union_stmt = union_all(attempt_stmt, problem_stmt).subquery()
        stmt = (
            select(union_stmt.c.memory_id, union_stmt.c.expansion_type)
            .distinct()
            .order_by(union_stmt.c.memory_id.asc())
        )
        return list(self._session.execute(stmt).mappings().all())

    def list_fact_update_neighbors(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns visible fact-update neighbors for an anchor memory."""

        old_stmt = (
            select(fact_updates.c.old_fact_id.label("memory_id"), literal("fact_update").label("expansion_type"))
            .select_from(fact_updates.join(memories, memories.c.id == fact_updates.c.old_fact_id))
            .where(
                or_(
                    fact_updates.c.change_id == anchor_memory_id,
                    fact_updates.c.new_fact_id == anchor_memory_id,
                ),
                *self._visibility_filters(repo_id=repo_id, include_global=include_global, kinds=kinds),
            )
        )
        change_stmt = (
            select(fact_updates.c.change_id.label("memory_id"), literal("fact_update").label("expansion_type"))
            .select_from(fact_updates.join(memories, memories.c.id == fact_updates.c.change_id))
            .where(
                or_(
                    fact_updates.c.old_fact_id == anchor_memory_id,
                    fact_updates.c.new_fact_id == anchor_memory_id,
                ),
                *self._visibility_filters(repo_id=repo_id, include_global=include_global, kinds=kinds),
            )
        )
        new_stmt = (
            select(fact_updates.c.new_fact_id.label("memory_id"), literal("fact_update").label("expansion_type"))
            .select_from(fact_updates.join(memories, memories.c.id == fact_updates.c.new_fact_id))
            .where(
                or_(
                    fact_updates.c.old_fact_id == anchor_memory_id,
                    fact_updates.c.change_id == anchor_memory_id,
                ),
                *self._visibility_filters(repo_id=repo_id, include_global=include_global, kinds=kinds),
            )
        )
        union_stmt = union_all(old_stmt, change_stmt, new_stmt).subquery()
        stmt = (
            select(union_stmt.c.memory_id, union_stmt.c.expansion_type)
            .where(union_stmt.c.memory_id != anchor_memory_id)
            .distinct()
            .order_by(union_stmt.c.memory_id.asc())
        )
        return list(self._session.execute(stmt).mappings().all())

    def list_association_neighbors(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
        min_strength: float,
    ) -> Sequence[dict[str, Any]]:
        """This method returns visible association neighbors for an anchor memory."""

        from_stmt = (
            select(
                association_edges.c.to_memory_id.label("memory_id"),
                association_edges.c.relation_type,
                association_edges.c.strength,
                literal("association").label("expansion_type"),
            )
            .select_from(association_edges.join(memories, memories.c.id == association_edges.c.to_memory_id))
            .where(
                association_edges.c.repo_id == repo_id,
                association_edges.c.from_memory_id == anchor_memory_id,
                association_edges.c.state != "deprecated",
                association_edges.c.strength >= min_strength,
                *self._visibility_filters(repo_id=repo_id, include_global=include_global, kinds=kinds),
            )
        )
        reverse_associated_stmt = (
            select(
                association_edges.c.from_memory_id.label("memory_id"),
                association_edges.c.relation_type,
                association_edges.c.strength,
                literal("association").label("expansion_type"),
            )
            .select_from(association_edges.join(memories, memories.c.id == association_edges.c.from_memory_id))
            .where(
                association_edges.c.repo_id == repo_id,
                association_edges.c.to_memory_id == anchor_memory_id,
                association_edges.c.relation_type == "associated_with",
                association_edges.c.state != "deprecated",
                association_edges.c.strength >= min_strength,
                *self._visibility_filters(repo_id=repo_id, include_global=include_global, kinds=kinds),
            )
        )
        union_stmt = union_all(from_stmt, reverse_associated_stmt).subquery()
        stmt = (
            select(
                union_stmt.c.memory_id,
                func.max(union_stmt.c.strength).label("strength"),
                literal("association").label("expansion_type"),
            )
            .where(union_stmt.c.memory_id != anchor_memory_id)
            .group_by(union_stmt.c.memory_id)
            .order_by(func.max(union_stmt.c.strength).desc(), union_stmt.c.memory_id.asc())
        )
        return list(self._session.execute(stmt).mappings().all())

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
