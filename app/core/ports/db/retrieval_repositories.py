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
        query_model: str | None = None,
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
        query_terms: Sequence[str] | None = None,
        candidate_limit: int | None = None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns visible text rows for lexical ranking."""


class IConceptSemanticRetrievalRepo(ABC):
    """This interface defines semantic-lane retrieval against concept embeddings."""

    @abstractmethod
    def query_concepts_semantic(
        self,
        *,
        repo_id: str,
        query_vector: Sequence[float],
        limit: int,
        query_model: str | None = None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns concept semantic retrieval candidates with scores."""


class IConceptKeywordRetrievalRepo(ABC):
    """This interface defines concept keyword-lane corpus access."""

    @abstractmethod
    def list_concept_keyword_corpus(
        self,
        *,
        repo_id: str,
        query_terms: Sequence[str] | None = None,
        candidate_limit: int | None = None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns active concept text rows for lexical ranking."""


class IReadPolicyRepo(ABC):
    """This interface defines read-path visibility and explicit expansion queries."""

    @abstractmethod
    def list_structural_memory_relation_rows(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
        predicates: Sequence[str],
    ) -> Sequence[dict[str, Any]]:
        """Return structural relation rows touching an anchor plus visible participants."""

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
