"""This module defines repository interfaces for relational and semantic data access."""

from abc import ABC, abstractmethod
from typing import Any, Sequence

from app.core.entities.associations import AssociationEdge, AssociationObservation
from app.core.entities.evidence import EvidenceRef
from app.core.entities.episodes import Episode, EpisodeEvent, SessionTransfer
from app.core.entities.facts import FactUpdate, ProblemAttempt
from app.core.entities.memory import Memory
from app.core.entities.utility import UtilityObservation


class IMemoriesRepo(ABC):
    """This interface defines persistence operations for memory aggregates."""

    @abstractmethod
    def create(self, memory: Memory) -> None:
        """This method persists a memory record."""

    @abstractmethod
    def get(self, memory_id: str) -> Memory | None:
        """This method fetches a memory by identifier."""

    @abstractmethod
    def list_by_ids(self, ids: Sequence[str]) -> Sequence[Memory]:
        """This method fetches memories in the input identifier order."""

    @abstractmethod
    def set_archived(self, *, memory_id: str, archived: bool) -> bool:
        """This method updates the archived state for a memory and reports whether a row changed."""

    @abstractmethod
    def upsert_embedding(self, *, memory_id: str, model: str, vector: Sequence[float]) -> None:
        """This method inserts or updates the embedding vector record for a memory."""


class IExperiencesRepo(ABC):
    """This interface defines persistence operations for problem attempts and fact updates."""

    @abstractmethod
    def create_problem_attempt(self, attempt: ProblemAttempt) -> None:
        """This method persists a problem-attempt link."""

    @abstractmethod
    def create_fact_update(self, fact_update: FactUpdate) -> None:
        """This method persists a fact-update chain row."""


class IAssociationsRepo(ABC):
    """This interface defines persistence operations for association edges and observations."""

    @abstractmethod
    def upsert_edge(self, edge: AssociationEdge) -> AssociationEdge:
        """This method inserts or updates an association edge."""

    @abstractmethod
    def append_observation(self, observation: AssociationObservation) -> None:
        """This method appends an immutable association observation."""


class IUtilityRepo(ABC):
    """This interface defines persistence operations for utility observations."""

    @abstractmethod
    def append_observation(self, observation: UtilityObservation) -> None:
        """This method appends a utility observation entry."""


class IEpisodesRepo(ABC):
    """This interface defines persistence operations for episodes and events."""

    @abstractmethod
    def create_episode(self, episode: Episode) -> None:
        """This method persists an episode row."""

    @abstractmethod
    def append_event(self, event: EpisodeEvent) -> None:
        """This method appends an event into an episode stream."""

    @abstractmethod
    def append_transfer(self, transfer: SessionTransfer) -> None:
        """This method appends a cross-session transfer row."""


class IEvidenceRepo(ABC):
    """This interface defines persistence operations for evidence references and links."""

    @abstractmethod
    def upsert_ref(self, repo_id: str, ref: str) -> EvidenceRef:
        """This method inserts or returns an evidence reference."""

    @abstractmethod
    def link_memory_evidence(self, memory_id: str, evidence_id: str) -> None:
        """This method links a memory to an evidence reference."""

    @abstractmethod
    def link_association_edge_evidence(self, edge_id: str, evidence_id: str) -> None:
        """This method links an association edge to an evidence reference."""


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
    """This interface defines keyword-lane retrieval against the lexical relevance engine."""

    @abstractmethod
    def query_keyword(
        self,
        *,
        repo_id: str,
        mode: str,
        include_global: bool,
        query_text: str,
        kinds: Sequence[str] | None,
        limit: int,
    ) -> Sequence[dict[str, Any]]:
        """This method returns lexical retrieval candidates with scores."""


class IReadPolicyRepo(ABC):
    """This interface defines read-path visibility and explicit expansion queries."""

    @abstractmethod
    def list_problem_attempt_neighbors(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns visible problem-attempt neighbors for an anchor memory."""

    @abstractmethod
    def list_fact_update_neighbors(
        self,
        *,
        repo_id: str,
        include_global: bool,
        anchor_memory_id: str,
        kinds: Sequence[str] | None,
    ) -> Sequence[dict[str, Any]]:
        """This method returns visible fact-update neighbors for an anchor memory."""

    @abstractmethod
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
