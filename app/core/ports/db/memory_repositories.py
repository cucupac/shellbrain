"""Repository ports for memory-domain persistence."""

from abc import ABC, abstractmethod
from typing import Sequence

from app.core.entities.associations import AssociationEdge, AssociationObservation
from app.core.entities.evidence import (
    EvidenceDetail,
    EvidenceLinkView,
    EvidenceRole,
    EvidenceSource,
    EvidenceTarget,
)
from app.core.entities.memories import Memory, MemoryLifecycleEvent
from app.core.entities.structural_memory_relations import StructuralMemoryRelation
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
    def list_recent(
        self, *, repo_id: str, statuses: Sequence[str], limit: int
    ) -> Sequence[Memory]:
        """Fetch recent memories for one repository in newest-first order."""

    @abstractmethod
    def update_lifecycle(self, memory: Memory) -> bool:
        """Update lifecycle fields for one concrete memory."""

    @abstractmethod
    def add_lifecycle_event(
        self, event: MemoryLifecycleEvent
    ) -> MemoryLifecycleEvent:
        """Append one auditable concrete memory lifecycle transition."""

    @abstractmethod
    def upsert_embedding(
        self, *, memory_id: str, model: str, vector: Sequence[float]
    ) -> None:
        """This method inserts or updates the embedding vector record for a memory."""


class IExperiencesRepo(ABC):
    """Persistence operations for curated structural memory relations."""

    @abstractmethod
    def upsert_structural_memory_relation(
        self, relation: StructuralMemoryRelation
    ) -> StructuralMemoryRelation:
        """This method inserts or returns one curated structural relation."""


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
    """This interface defines the unified evidence attach and resolve boundary."""

    @abstractmethod
    def attach_evidence(
        self,
        *,
        repo_id: str,
        target: EvidenceTarget,
        sources: Sequence[EvidenceSource],
        role: EvidenceRole = EvidenceRole.SUPPORTS,
    ) -> Sequence[EvidenceLinkView]:
        """Attach evidence sources to one target through the unified evidence API."""

    @abstractmethod
    def resolve_evidence(
        self, *, repo_id: str, targets: Sequence[EvidenceTarget]
    ) -> Sequence[EvidenceLinkView]:
        """Resolve evidence links for targets through the unified evidence API."""

    @abstractmethod
    def get_evidence_detail(
        self, *, repo_id: str, evidence_id: str
    ) -> EvidenceDetail | None:
        """Resolve one canonical evidence source plus linked targets."""
