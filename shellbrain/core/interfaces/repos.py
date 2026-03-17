"""This module defines repository interfaces for relational and semantic data access."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Sequence

from shellbrain.core.entities.associations import AssociationEdge, AssociationObservation
from shellbrain.core.entities.evidence import EvidenceRef
from shellbrain.core.entities.episodes import Episode, EpisodeEvent, SessionTransfer
from shellbrain.core.entities.facts import FactUpdate, ProblemAttempt
from shellbrain.core.entities.memory import Memory
from shellbrain.core.entities.utility import UtilityObservation


class IMemoriesRepo(ABC):
    """This interface defines persistence operations for shellbrain aggregates."""

    @abstractmethod
    def create(self, memory: Memory) -> None:
        """This method persists a shellbrain record."""

    @abstractmethod
    def get(self, memory_id: str) -> Memory | None:
        """This method fetches a shellbrain by identifier."""

    @abstractmethod
    def list_by_ids(self, ids: Sequence[str]) -> Sequence[Memory]:
        """This method fetches memories in the input identifier order."""

    @abstractmethod
    def set_archived(self, *, memory_id: str, archived: bool) -> bool:
        """This method updates the archived state for a shellbrain and reports whether a row changed."""

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
    def get_episode_by_thread(
        self,
        *,
        repo_id: str,
        thread_id: str,
    ) -> Episode | None:
        """This method fetches one episode by canonical host session key."""

    @abstractmethod
    def list_event_keys(self, *, episode_id: str) -> Sequence[str]:
        """This method returns already-imported upstream event keys for one episode."""

    @abstractmethod
    def next_event_seq(self, *, episode_id: str) -> int:
        """This method returns the next append sequence number for one episode."""

    @abstractmethod
    def append_event(self, event: EpisodeEvent) -> None:
        """This method appends an event into an episode stream."""

    @abstractmethod
    def close_episode(self, *, episode_id: str, ended_at: datetime) -> None:
        """This method marks an active episode closed."""

    @abstractmethod
    def append_transfer(self, transfer: SessionTransfer) -> None:
        """This method appends a cross-session transfer row."""

    @abstractmethod
    def list_existing_event_ids(self, *, event_ids: Sequence[str]) -> Sequence[str]:
        """This method returns episode-event ids that exist anywhere in storage."""

    @abstractmethod
    def list_visible_event_ids(self, *, repo_id: str, event_ids: Sequence[str]) -> Sequence[str]:
        """This method returns episode-event ids visible within one repo."""

    @abstractmethod
    def list_recent_events(
        self,
        *,
        repo_id: str,
        episode_id: str,
        limit: int,
    ) -> Sequence[EpisodeEvent]:
        """This method returns recent events for one visible episode ordered newest first."""


class IEvidenceRepo(ABC):
    """This interface defines persistence operations for evidence references and links."""

    @abstractmethod
    def upsert_ref(self, repo_id: str, ref: str) -> EvidenceRef:
        """This method inserts or returns an evidence reference."""

    @abstractmethod
    def link_memory_evidence(self, memory_id: str, evidence_id: str) -> None:
        """This method links a shellbrain to an evidence reference."""

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
