"""This module defines repository interfaces for relational and semantic data access."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Sequence

from app.core.entities.associations import AssociationEdge, AssociationObservation
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
from app.core.entities.evidence import EvidenceRef
from app.core.entities.episodes import Episode, EpisodeEvent, SessionTransfer
from app.core.entities.facts import FactUpdate, ProblemAttempt
from app.core.entities.memory import Memory
from app.core.entities.telemetry import (
    EpisodeSyncRunRecord,
    EpisodeSyncToolTypeRecord,
    ModelUsageRecord,
    OperationInvocationRecord,
    RecallSourceItemRecord,
    RecallSummaryRecord,
    ReadResultItemRecord,
    ReadSummaryRecord,
    WriteEffectItemRecord,
    WriteSummaryRecord,
)
from app.core.entities.guidance import PendingUtilityCandidate
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


class IConceptsRepo(ABC):
    """This interface defines persistence operations for the concept-context graph."""

    @abstractmethod
    def upsert_concept(self, concept: Concept, aliases: Sequence[str]) -> Concept:
        """This method inserts or updates a concept and its aliases."""

    @abstractmethod
    def get_concept_by_ref(self, *, repo_id: str, concept_ref: str) -> Concept | None:
        """This method resolves a concept by id or slug."""

    @abstractmethod
    def list_concepts_by_ids(self, *, repo_id: str, concept_ids: Sequence[str]) -> Sequence[Concept]:
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
    def get_concept_bundle(self, *, repo_id: str, concept_ref: str) -> dict[str, Any] | None:
        """This method returns one concept plus directly related graph records."""

    @abstractmethod
    def find_concepts_for_memory_ids(self, *, repo_id: str, memory_ids: Sequence[str]) -> Sequence[dict[str, Any]]:
        """This method returns concept-link matches for displayed memory ids."""

    @abstractmethod
    def list_concept_search_rows(self, *, repo_id: str) -> Sequence[dict[str, Any]]:
        """This method returns active concept text rows for query matching."""


class IEpisodesRepo(ABC):
    """This interface defines persistence operations for episodes and events."""

    @abstractmethod
    def create_episode(self, episode: Episode) -> None:
        """This method persists an episode row."""

    @abstractmethod
    def acquire_thread_sync_guard(self, *, repo_id: str, thread_id: str) -> None:
        """This method serializes sync writes for one repo/thread pair."""

    @abstractmethod
    def get_or_create_episode_for_thread(self, episode: Episode) -> Episode:
        """This method returns the canonical episode row for one thread, creating it when missing."""

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
    def append_event_if_new(self, event: EpisodeEvent) -> bool:
        """This method appends an event only when its host_event_key is not already present."""

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


class ITelemetryRepo(ABC):
    """This interface defines append-heavy telemetry persistence operations."""

    @abstractmethod
    def insert_operation_invocation(self, record: OperationInvocationRecord) -> None:
        """This method appends one command-level telemetry row."""

    @abstractmethod
    def insert_read_summary(
        self,
        summary: ReadSummaryRecord,
        items: Sequence[ReadResultItemRecord],
    ) -> None:
        """This method persists one read summary row and its ordered result items."""

    @abstractmethod
    def insert_recall_summary(
        self,
        summary: RecallSummaryRecord,
        items: Sequence[RecallSourceItemRecord],
    ) -> None:
        """This method persists one recall summary row and its ordered source items."""

    @abstractmethod
    def insert_write_summary(
        self,
        summary: WriteSummaryRecord,
        items: Sequence[WriteEffectItemRecord],
    ) -> None:
        """This method persists one write summary row and its ordered effect items."""

    @abstractmethod
    def insert_episode_sync_run(
        self,
        run: EpisodeSyncRunRecord,
        tool_types: Sequence[EpisodeSyncToolTypeRecord],
    ) -> None:
        """This method appends one sync-run row and its per-tool aggregates."""

    @abstractmethod
    def insert_model_usage(self, records: Sequence[ModelUsageRecord]) -> None:
        """This method appends normalized model-usage rows idempotently."""

    @abstractmethod
    def update_operation_polling(self, invocation_id: str, *, attempted: bool, started: bool) -> None:
        """This method patches the poller-start flags for one existing invocation row."""

    @abstractmethod
    def list_pending_utility_candidates(
        self,
        *,
        repo_id: str,
        caller_id: str,
        problem_id: str,
        since_iso: str,
    ) -> Sequence[PendingUtilityCandidate]:
        """This method returns retrieved memories that still lack a utility vote for one problem."""
