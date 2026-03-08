"""This module defines keyword-lane retrieval operations backed by app-side BM25."""

from __future__ import annotations

from typing import Any, Literal, Sequence

from sqlalchemy import select

from app.core.policies.read_policy.bm25 import BM25Document, admit_scored_documents, score_documents
from app.core.policies.read_policy.lexical_query import build_lexical_query, normalize_lexical_text
from app.core.interfaces.repos import IKeywordRetrievalRepo
from app.periphery.db.models.memories import memories


class KeywordRetrievalRepo(IKeywordRetrievalRepo):
    """This class provides lexical retrieval candidates from app-side BM25 scoring."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for keyword retrieval operations."""

        self._session = session

    def query_keyword(
        self,
        *,
        repo_id: str,
        mode: Literal["ambient", "targeted"],
        include_global: bool,
        query_text: str,
        kinds: Sequence[str] | None,
        limit: int,
    ) -> Sequence[dict[str, Any]]:
        """This method returns keyword candidates and lexical ranking scores."""

        lexical_query = build_lexical_query(query_text)
        if not lexical_query.terms:
            return []

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

        documents = [
            BM25Document(
                memory_id=str(row["memory_id"]),
                terms=normalize_lexical_text(str(row["text"])).terms_for(lexical_query),
            )
            for row in self._session.execute(stmt).mappings().all()
        ]
        scored_documents = score_documents(lexical_query.terms, documents)
        return admit_scored_documents(scored_documents, mode=mode)[:limit]
