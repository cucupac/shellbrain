"""Repository ports for concept graph persistence."""

from abc import ABC, abstractmethod
from typing import Any, Sequence

from app.core.entities.concepts import (
    Anchor,
    Concept,
    ConceptClaim,
    ConceptEvidence,
    ConceptGrounding,
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
    def add_evidence(self, evidence: ConceptEvidence) -> ConceptEvidence:
        """This method appends one evidence pointer for a concept graph record."""

    @abstractmethod
    def create_graph_patch(self, patch: GraphPatch) -> GraphPatch:
        """This method stores one future graph-patch proposal record."""

    @abstractmethod
    def get_concept_bundle(
        self, *, repo_id: str, concept_ref: str
    ) -> dict[str, Any] | None:
        """This method returns one concept plus directly related graph records."""

    @abstractmethod
    def find_concepts_for_memory_ids(
        self, *, repo_id: str, memory_ids: Sequence[str]
    ) -> Sequence[dict[str, Any]]:
        """This method returns concept-link matches for displayed memory ids."""

    @abstractmethod
    def list_concept_search_rows(self, *, repo_id: str) -> Sequence[dict[str, Any]]:
        """This method returns active concept text rows for query matching."""
