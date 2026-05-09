"""Repository ports for memory-domain persistence."""

from abc import ABC, abstractmethod
from typing import Sequence

from app.core.entities.associations import AssociationEdge, AssociationObservation
from app.core.entities.evidence import EvidenceRef
from app.core.entities.facts import FactUpdate, ProblemAttempt
from app.core.entities.memories import Memory
from app.core.entities.utility import UtilityObservation


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
    def upsert_embedding(
        self, *, memory_id: str, model: str, vector: Sequence[float]
    ) -> None:
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
