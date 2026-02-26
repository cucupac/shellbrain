"""This module defines keyword-lane retrieval operations backed by PostgreSQL FTS."""

from typing import Any, Sequence

from app.core.interfaces.repos import IKeywordRetrievalRepo


class KeywordRetrievalRepo(IKeywordRetrievalRepo):
    """This class provides lexical retrieval candidates from PostgreSQL FTS."""

    def __init__(self, session) -> None:
        """This method stores the active DB session for keyword retrieval operations."""

        self._session = session

    def query_keyword(self, *, repo_id: str, query_text: str, kinds: Sequence[str] | None, limit: int) -> Sequence[dict[str, Any]]:
        """This method returns keyword candidates and lexical ranking scores."""

        # TODO: Implement tsquery-based lookup with scope/kind filters.
        _ = (repo_id, query_text, kinds, limit)
        return []
