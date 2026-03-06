"""This module defines keyword-lane retrieval operations backed by PostgreSQL FTS."""

from __future__ import annotations

import re
from typing import Any, Sequence

from sqlalchemy import func, select

from app.core.interfaces.repos import IKeywordRetrievalRepo
from app.periphery.db.models.memories import memories


class KeywordRetrievalRepo(IKeywordRetrievalRepo):
    """This class provides lexical retrieval candidates from PostgreSQL FTS."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for keyword retrieval operations."""

        self._session = session

    def query_keyword(
        self,
        *,
        repo_id: str,
        include_global: bool,
        query_text: str,
        kinds: Sequence[str] | None,
        limit: int,
    ) -> Sequence[dict[str, Any]]:
        """This method returns keyword candidates and lexical ranking scores."""

        tokens = _normalize_query_tokens(query_text)
        if not tokens:
            return []

        tsquery_text = " | ".join(f"{token}:*" for token in tokens)
        query = func.to_tsquery("english", tsquery_text)
        vector = func.to_tsvector("english", memories.c.text)
        rank = func.ts_rank_cd(vector, query)
        scope_values = ["repo", "global"] if include_global else ["repo"]

        stmt = (
            select(
                memories.c.id.label("memory_id"),
                rank.label("score"),
            )
            .where(
                memories.c.repo_id == repo_id,
                memories.c.archived.is_(False),
                memories.c.scope.in_(scope_values),
                vector.op("@@")(query),
            )
            .order_by(rank.desc(), memories.c.id.asc())
            .limit(limit)
        )
        if kinds:
            stmt = stmt.where(memories.c.kind.in_(list(kinds)))

        return list(self._session.execute(stmt).mappings().all())


def _normalize_query_tokens(query_text: str) -> list[str]:
    """Normalize free text into a deterministic set of prefix-search tokens."""

    return [token for token in re.findall(r"[a-z0-9]+", query_text.lower()) if token]
