"""This module defines visibility-gated keyword corpus access."""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select

from app.core.ports.db.retrieval_repositories import IKeywordRetrievalRepo
from app.infrastructure.db.runtime.models.memories import memories


class KeywordRetrievalRepo(IKeywordRetrievalRepo):
    """This class provides visible text rows for core lexical ranking."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for keyword retrieval operations."""

        self._session = session

    def list_keyword_corpus(
        self,
        *,
        repo_id: str,
        include_global: bool,
        kinds: Sequence[str] | None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns visible memory text rows for lexical ranking."""

        scope_values = ["repo", "global"] if include_global else ["repo"]
        stmt = (
            select(
                memories.c.id.label("memory_id"),
                memories.c.text,
            )
            .where(
                memories.c.repo_id == repo_id,
                memories.c.archived.is_(False),
                memories.c.scope.in_(scope_values),
            )
            .order_by(memories.c.id.asc())
        )
        if kinds:
            stmt = stmt.where(memories.c.kind.in_(list(kinds)))

        return [
            {"memory_id": str(row["memory_id"]), "text": str(row["text"])}
            for row in self._session.execute(stmt).mappings().all()
        ]
