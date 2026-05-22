"""This module defines visibility-gated keyword corpus access."""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import desc, func, literal_column, select

from app.core.entities.memories import DEFAULT_RETRIEVABLE_MEMORY_STATUS_VALUES
from app.core.ports.db.retrieval_repositories import IKeywordRetrievalRepo
from app.infrastructure.db.runtime.models.memories import memories


_ENGLISH_REGCONFIG = literal_column("'english'")


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
        query_terms: Sequence[str] | None = None,
        candidate_limit: int | None = None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns visible memory text rows for lexical ranking."""

        ranked_rows = self._ranked_fts_rows(
            repo_id=repo_id,
            include_global=include_global,
            kinds=kinds,
            query_terms=query_terms,
            candidate_limit=candidate_limit,
        )
        if ranked_rows:
            return ranked_rows

        return self._visible_corpus_rows(
            repo_id=repo_id,
            include_global=include_global,
            kinds=kinds,
        )

    def _ranked_fts_rows(
        self,
        *,
        repo_id: str,
        include_global: bool,
        kinds: Sequence[str] | None,
        query_terms: Sequence[str] | None,
        candidate_limit: int | None,
    ) -> list[dict[str, Any]]:
        """Return an indexed FTS candidate pool before pure BM25 reranking."""

        query_string = _websearch_or_query(query_terms)
        if not query_string:
            return []

        ts_vector = func.to_tsvector(_ENGLISH_REGCONFIG, memories.c.text)
        ts_query = func.websearch_to_tsquery(_ENGLISH_REGCONFIG, query_string)
        rank = func.ts_rank_cd(ts_vector, ts_query)
        stmt = (
            select(
                memories.c.id.label("memory_id"),
                memories.c.text,
                memories.c.status,
            )
            .where(
                *self._visibility_filters(
                    repo_id=repo_id,
                    include_global=include_global,
                    kinds=kinds,
                ),
                ts_vector.op("@@")(ts_query),
            )
            .order_by(desc(rank), memories.c.id.asc())
        )
        if candidate_limit is not None and candidate_limit > 0:
            stmt = stmt.limit(int(candidate_limit))

        return _rows_to_corpus(self._session.execute(stmt).mappings().all())

    def _visible_corpus_rows(
        self,
        *,
        repo_id: str,
        include_global: bool,
        kinds: Sequence[str] | None,
    ) -> list[dict[str, Any]]:
        """Return the full visible corpus when indexed prefiltering cannot narrow it."""

        scope_values = ["repo", "global"] if include_global else ["repo"]
        stmt = (
            select(
                memories.c.id.label("memory_id"),
                memories.c.text,
                memories.c.status,
            )
            .where(
                memories.c.repo_id == repo_id,
                memories.c.status.in_(list(DEFAULT_RETRIEVABLE_MEMORY_STATUS_VALUES)),
                memories.c.scope.in_(scope_values),
            )
            .order_by(memories.c.id.asc())
        )
        if kinds:
            stmt = stmt.where(memories.c.kind.in_(list(kinds)))

        return _rows_to_corpus(self._session.execute(stmt).mappings().all())

    def _visibility_filters(
        self,
        *,
        repo_id: str,
        include_global: bool,
        kinds: Sequence[str] | None,
    ) -> list[Any]:
        """Build the visibility filters used by keyword retrieval queries."""

        scope_values = ["repo", "global"] if include_global else ["repo"]
        filters: list[Any] = [
            memories.c.repo_id == repo_id,
            memories.c.status.in_(list(DEFAULT_RETRIEVABLE_MEMORY_STATUS_VALUES)),
            memories.c.scope.in_(scope_values),
        ]
        if kinds:
            filters.append(memories.c.kind.in_(list(kinds)))
        return filters


def _rows_to_corpus(rows: Sequence[Any]) -> list[dict[str, Any]]:
    """Normalize SQL rows into the keyword corpus shape expected by core policy."""

    return [
        {
            "memory_id": str(row["memory_id"]),
            "text": str(row["text"]),
            "status": str(row["status"]),
        }
        for row in rows
    ]


def _websearch_or_query(query_terms: Sequence[str] | None) -> str:
    """Build a safe OR query from already-normalized lexical terms."""

    if not query_terms:
        return ""
    terms = [str(term).strip() for term in query_terms if str(term).strip()]
    return " OR ".join(terms)
