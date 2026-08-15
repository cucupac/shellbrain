"""Repository ports for concept graph persistence."""

from abc import ABC, abstractmethod
from typing import Any, Sequence

from app.core.entities.concepts import (
    Anchor,
    Concept,
    ConceptClaim,
    ConceptGrounding,
    ConceptLifecycleEvent,
    ConceptLifecycleTargetType,
    ConceptMemoryLink,
    ConceptRelation,
    GraphPatch,
)


class IConceptsRepo(ABC):
    """This interface defines persistence operations for the concept-context graph."""

    @abstractmethod
    def add_concept(self, concept: Concept, aliases: Sequence[str]) -> Concept:
        """This method inserts a new concept and its aliases."""

    @abstractmethod
    def update_concept(self, concept: Concept, aliases: Sequence[str]) -> Concept:
        """This method updates an existing concept and adds aliases."""

    @abstractmethod
    def get_concept_by_ref(self, *, repo_id: str, concept_ref: str) -> Concept | None:
        """This method resolves a concept by id or slug."""

    @abstractmethod
    def list_concepts_by_ids(
        self, *, repo_id: str, concept_ids: Sequence[str]
    ) -> Sequence[Concept]:
        """This method returns concepts for the provided ids."""

    @abstractmethod
    def list_contains_edges(self, *, repo_id: str) -> Sequence[ConceptRelation]:
        """This method returns active contains edges for cycle validation."""

    @abstractmethod
    def add_relation(self, relation: ConceptRelation) -> ConceptRelation:
        """This method inserts or returns an active concept relation."""

    @abstractmethod
    def add_claim(self, claim: ConceptClaim) -> ConceptClaim:
        """This method inserts or returns a concept claim."""

    @abstractmethod
    def upsert_anchor(self, anchor: Anchor) -> Anchor:
        """This method inserts or returns an anchor by canonical locator."""

    @abstractmethod
    def get_anchor(self, *, repo_id: str, anchor_id: str) -> Anchor | None:
        """This method fetches one anchor by id."""

    @abstractmethod
    def add_grounding(self, grounding: ConceptGrounding) -> ConceptGrounding:
        """This method inserts or returns an active concept grounding."""

    @abstractmethod
    def add_memory_link(self, memory_link: ConceptMemoryLink) -> ConceptMemoryLink:
        """This method inserts or returns an active concept-memory link."""

    @abstractmethod
    def get_lifecycle_target(
        self, *, repo_id: str, target_type: ConceptLifecycleTargetType, target_id: str
    ) -> ConceptRelation | ConceptClaim | ConceptGrounding | ConceptMemoryLink | None:
        """This method fetches one truth-bearing concept record by lifecycle target."""

    @abstractmethod
    def update_lifecycle_target(
        self,
        target: ConceptRelation | ConceptClaim | ConceptGrounding | ConceptMemoryLink,
    ) -> ConceptRelation | ConceptClaim | ConceptGrounding | ConceptMemoryLink:
        """This method updates lifecycle fields for one truth-bearing concept record."""

    @abstractmethod
    def add_lifecycle_event(
        self, event: ConceptLifecycleEvent
    ) -> ConceptLifecycleEvent:
        """This method appends one auditable concept lifecycle transition."""

    @abstractmethod
    def create_graph_patch(self, patch: GraphPatch) -> GraphPatch:
        """This method stores one future graph-patch proposal record."""

    @abstractmethod
    def get_concept_bundle(
        self,
        *,
        repo_id: str,
        concept_ref: str,
        include_lifecycle_events: bool = False,
    ) -> dict[str, Any] | None:
        """This method returns one concept plus directly related graph records."""

    @abstractmethod
    def find_concepts_for_memory_ids(
        self, *, repo_id: str, memory_ids: Sequence[str]
    ) -> Sequence[dict[str, Any]]:
        """This method returns concept-link matches for displayed memory ids."""

    @abstractmethod
    def upsert_embedding(
        self,
        *,
        concept_id: str,
        repo_id: str,
        model: str,
        vector: Sequence[float],
        source_hash: str,
    ) -> None:
        """This method inserts or updates one aggregate concept embedding."""
