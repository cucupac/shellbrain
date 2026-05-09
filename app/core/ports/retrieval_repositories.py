"""Repository ports for retrieval capabilities."""

from abc import ABC, abstractmethod
from typing import Any, Sequence


class ISemanticRetrievalRepo(ABC):
    """This interface defines semantic-lane retrieval against embeddings."""

    @abstractmethod
    def query_semantic(
        self,
        *,
        repo_id: str,
        include_global: bool,
        query_vector: Sequence[float],
        kinds: Sequence[str] | None,
        limit: int,
    ) -> Sequence[dict[str, Any]]:
        """This method returns semantic retrieval candidates with scores."""

    @abstractmethod
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


class IKeywordRetrievalRepo(ABC):
    """This interface defines keyword-lane corpus access."""

    @abstractmethod
    def list_keyword_corpus(
        self,
        *,
        repo_id: str,
        include_global: bool,
        kinds: Sequence[str] | None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns visible text rows for lexical ranking."""


class IReadPolicyRepo(ABC):
    """This interface defines read-path visibility and explicit expansion queries."""

    @abstractmethod
    def list_problem_attempt_rows(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns problem-attempt rows touching an anchor plus visible participants."""

    @abstractmethod
    def list_fact_update_rows(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns fact-update rows touching an anchor plus visible participants."""

    @abstractmethod
    def list_association_edge_rows(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns visible active association edge rows touching an anchor."""
