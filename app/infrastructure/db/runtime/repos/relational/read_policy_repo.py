"""This module defines SQL-backed read-path visibility and explicit expansion queries."""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import or_, select

from app.core.policies.retrieval.ontology_semantics import POSITIVE_LIFECYCLE_STATUSES
from app.core.ports.db.retrieval_repositories import IReadPolicyRepo
from app.infrastructure.db.runtime.models.experiences import structural_memory_relations
from app.infrastructure.db.runtime.models.memories import memories
from app.infrastructure.db.runtime.repos.memory_visibility import visible_memory_filters


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
                *visible_memory_filters(
                    repo_id=repo_id, include_global=include_global, kinds=kinds
                ),
            )
        )
        return {str(row[0]) for row in rows}
