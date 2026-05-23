"""Unit coverage for deterministic graph-first recall packing."""

from __future__ import annotations

from app.core.entities.concepts import (
    Anchor,
    AnchorKind,
    Concept,
    ConceptClaim,
    ConceptClaimType,
    ConceptGrounding,
    ConceptGroundingRole,
    ConceptKind,
    ConceptLifecycle,
    ConceptLifecycleStatus,
    ConceptMemoryLink,
    ConceptMemoryLinkRole,
    ConceptRelation,
    ConceptRelationPredicate,
)
from app.core.entities.ids import MemoryId, RepoId
from app.core.entities.memories import Memory, MemoryKind, MemoryScope
from app.core.use_cases.retrieval.deterministic_graph_recall import (
    _build_query_lanes,
    build_deterministic_graph_pack,
    source_items_from_graph_pack,
)
from app.core.use_cases.retrieval.recall.request import MemoryRecallRequest


def test_query_lanes_omit_placeholder_current_problem_values() -> None:
    """query lane construction should not preserve empty problem placeholders."""

    request = _request(
        query='Debug `app/core/settings.py` "TimeoutError" SB-123 v1.2',
        hypothesis="none yet",
    )

    lanes = _build_query_lanes(request)
    lane_queries = {lane.name: lane.query for lane in lanes}

    assert "none yet" not in " ".join(lane_queries.values()).lower()
    assert "app/core/settings.py" in lane_queries["identifiers"]
    assert "TimeoutError" in lane_queries["identifiers"]
    assert "SB-123" in lane_queries["identifiers"]
    assert "v1.2" in lane_queries["identifiers"]


def test_graph_pack_discovers_concepts_without_memory_links_and_pulls_graph_context() -> None:
    """concept retrieval should feed graph traversal even without memory fanout links."""

    uow = _FakeUow()

    pack = build_deterministic_graph_pack(
        request=_request(query="TimeoutError in app/core/settings.py"),
        uow=uow,
    )

    concept_refs = {concept["ref"] for concept in pack["concepts"]}
    memory_by_id = {memory["id"]: memory for memory in pack["memories"]}
    neighbor_refs = {concept["ref"] for concept in pack["relation_neighbors"]}

    assert concept_refs == {"db-admin"}
    assert "mem-direct" in memory_by_id
    assert "mem-warning" in memory_by_id
    assert "mem-change" in memory_by_id
    assert "mem-change-context" in memory_by_id
    assert "graph_linked_memory" in memory_by_id["mem-warning"]["why"]
    assert "warns_about" in memory_by_id["mem-warning"]["link_roles"]
    assert memory_by_id["mem-warning"]["currentness"] == "historical_warning"
    assert memory_by_id["mem-change"]["currentness"] == "current"
    assert memory_by_id["mem-change-context"]["currentness"] == "current"
    assert neighbor_refs == {"postgres-migrations"}
    assert any(anchor["locator"] == "app/core/settings.py" for anchor in pack["anchors"])
    assert pack["concepts"][0]["currentness"] == "stale"
    assert any(
        claim["currentness"] == "stale" for claim in pack["concepts"][0]["claims"]
    )
    conflict_types = {conflict["type"] for conflict in pack["conflicts"]}
    assert "stale_claim" in conflict_types
    assert pack["pack_trace"]["concept_candidates"]["candidate_count"] >= 1
    assert pack["pack_trace"]["graph_traversal"]["linked_memories_loaded"] == 3
    assert pack["pack_trace"]["graph_traversal"]["relation_neighbors_loaded"] == 1


def test_graph_pack_does_not_select_archived_concept_records_as_signal() -> None:
    """archived concept records should not produce positive graph-recall signal."""

    uow = _FakeUow()
    uow.concepts = _ArchivedFakeConcepts()

    pack = build_deterministic_graph_pack(
        request=_request(query="TimeoutError in app/core/settings.py"),
        uow=uow,
    )

    assert pack["concepts"] == []
    memory_by_id = {memory["id"]: memory for memory in pack["memories"]}
    assert memory_by_id["mem-direct"]["currentness"] == "current"
    assert memory_by_id["mem-direct"]["link_roles"] == []
    assert memory_by_id["mem-direct"]["concept_refs"] == []
    assert pack["pack_trace"]["concept_candidates"]["candidate_count"] >= 1
    assert pack["pack_trace"]["concept_candidates"]["selected"] == 0


def test_graph_pack_expands_canonical_structural_memory_relations() -> None:
    """deterministic recall should use structural relations as explicit memory context."""

    uow = _FakeUow()
    uow.concepts = _NoFakeConcepts()
    uow.concept_semantic_retrieval = _NoFakeConceptSemanticRetrieval()
    uow.read_policy = _StructuralFakeReadPolicy()

    pack = build_deterministic_graph_pack(
        request=_request(query="TimeoutError in app/core/settings.py"),
        uow=uow,
    )

    memory_by_id = {memory["id"]: memory for memory in pack["memories"]}
    assert "mem-change" in memory_by_id
    assert "structural_memory_relation" in memory_by_id["mem-change"]["why"]
    assert pack["pack_trace"]["structural_memory_relations"] == {
        "expanded_memory_count": 1,
        "relation_count": 1,
        "relation_count_by_type": {"explained_by_change": 1},
    }
    sources_by_id = {
        source["source_id"]: source
        for source in source_items_from_graph_pack(pack)
        if source["source_kind"] == "memory"
    }
    assert sources_by_id["mem-change"]["input_section"] == "explicit_related"


def _request(*, query: str, hypothesis: str = "missing timeout guard") -> MemoryRecallRequest:
    return MemoryRecallRequest.model_validate(
        {
            "op": "recall",
            "repo_id": "repo-a",
            "query": query,
            "current_problem": {
                "goal": "fix migration",
                "surface": "db admin app/core/settings.py",
                "obstacle": "TimeoutError while loading config",
                "hypothesis": hypothesis,
            },
        }
    )


class _FakeVectorSearch:
    model_name = "fake-embedding"

    def embed_query(self, query: str) -> list[float]:
        return [float(len(query) % 7) + 1.0]


class _FakeSemanticRetrieval:
    def query_semantic(self, **kwargs):
        del kwargs
        return [{"memory_id": "mem-direct", "score": 0.92}]


class _FakeKeywordRetrieval:
    def list_keyword_corpus(self, **kwargs):
        del kwargs
        return []


class _FakeConceptSemanticRetrieval:
    def query_concepts_semantic(self, **kwargs):
        del kwargs
        return [{"concept_id": "c-db", "score": 0.91}]


class _NoFakeConceptSemanticRetrieval:
    def query_concepts_semantic(self, **kwargs):
        del kwargs
        return []


class _FakeConceptKeywordRetrieval:
    def list_concept_keyword_corpus(self, **kwargs):
        del kwargs
        return []


class _FakeMemories:
    def __init__(self) -> None:
        self._memories = {
            "mem-direct": Memory(
                id=MemoryId("mem-direct"),
                repo_id=RepoId("repo-a"),
                scope=MemoryScope.REPO,
                kind=MemoryKind.FACT,
                text="Config loading can raise TimeoutError during migration setup.",
            ),
            "mem-warning": Memory(
                id=MemoryId("mem-warning"),
                repo_id=RepoId("repo-a"),
                scope=MemoryScope.REPO,
                kind=MemoryKind.FAILED_TACTIC,
                text="Retrying migrations without checking the config timeout failed.",
            ),
            "mem-change": Memory(
                id=MemoryId("mem-change"),
                repo_id=RepoId("repo-a"),
                scope=MemoryScope.REPO,
                kind=MemoryKind.CHANGE,
                text="Timeout handling moved into the app settings loader.",
            ),
            "mem-change-context": Memory(
                id=MemoryId("mem-change-context"),
                repo_id=RepoId("repo-a"),
                scope=MemoryScope.REPO,
                kind=MemoryKind.FACT,
                text="Old timeout guidance is relevant when reviewing current migration settings.",
            ),
        }

    def list_by_ids(self, memory_ids):
        return [
            self._memories[memory_id]
            for memory_id in memory_ids
            if memory_id in self._memories
        ]


class _FakeConcepts:
    def __init__(self) -> None:
        self._concept = Concept(
            id="c-db",
            repo_id="repo-a",
            slug="db-admin",
            name="DB Admin",
            kind=ConceptKind.PROCESS,
        )
        self._neighbor = Concept(
            id="c-pg",
            repo_id="repo-a",
            slug="postgres-migrations",
            name="Postgres Migrations",
            kind=ConceptKind.PROCESS,
        )
        self._anchor = Anchor(
            id="anchor-settings",
            repo_id="repo-a",
            kind=AnchorKind.FILE,
            locator_json={"path": "app/core/settings.py"},
            canonical_locator_hash="settings-hash",
        )

    def find_concepts_for_memory_ids(self, **kwargs):
        del kwargs
        return []

    def get_concept_bundle(self, *, repo_id: str, concept_ref: str):
        if repo_id != "repo-a":
            return None
        if concept_ref == "c-db":
            return {
                "concept": self._concept,
                "aliases": [],
                "claims": [
                    ConceptClaim(
                        id="claim-failure",
                        repo_id="repo-a",
                        concept_id="c-db",
                        claim_type=ConceptClaimType.FAILURE_MODE,
                        text="TimeoutError can indicate stale migration configuration.",
                        normalized_text="timeouterror can indicate stale migration configuration",
                    ),
                    ConceptClaim(
                        id="claim-stale",
                        repo_id="repo-a",
                        concept_id="c-db",
                        claim_type=ConceptClaimType.USAGE_NOTE,
                        text="Old migrations read timeout settings from the CLI env.",
                        normalized_text="old migrations read timeout settings from the cli env",
                        lifecycle=ConceptLifecycle(
                            status=ConceptLifecycleStatus.STALE,
                            confidence=0.4,
                        ),
                    ),
                ],
                "relations": [
                    ConceptRelation(
                        id="relation-depends",
                        repo_id="repo-a",
                        subject_concept_id="c-db",
                        predicate=ConceptRelationPredicate.DEPENDS_ON,
                        object_concept_id="c-pg",
                    )
                ],
                "anchors": [self._anchor],
                "groundings": [
                    ConceptGrounding(
                        id="grounding-settings",
                        repo_id="repo-a",
                        concept_id="c-db",
                        role=ConceptGroundingRole.IMPLEMENTATION,
                        anchor_id="anchor-settings",
                    )
                ],
                "memory_links": [
                    ConceptMemoryLink(
                        id="link-warning",
                        repo_id="repo-a",
                        concept_id="c-db",
                        role=ConceptMemoryLinkRole.WARNS_ABOUT,
                        memory_id="mem-warning",
                    ),
                    ConceptMemoryLink(
                        id="link-change",
                        repo_id="repo-a",
                        concept_id="c-db",
                        role=ConceptMemoryLinkRole.CHANGE_RELEVANT_TO,
                        memory_id="mem-change",
                    ),
                    ConceptMemoryLink(
                        id="link-change-context",
                        repo_id="repo-a",
                        concept_id="c-db",
                        role=ConceptMemoryLinkRole.CHANGE_RELEVANT_TO,
                        memory_id="mem-change-context",
                    ),
                ],
                "evidence": [],
            }
        if concept_ref == "c-pg":
            return {
                "concept": self._neighbor,
                "aliases": [],
                "claims": [],
                "relations": [],
                "anchors": [],
                "groundings": [],
                "memory_links": [],
                "evidence": [],
            }
        return None


class _ArchivedFakeConcepts(_FakeConcepts):
    def find_concepts_for_memory_ids(self, **kwargs):
        del kwargs
        return [
            {
                "concept_id": "c-db",
                "memory_id": "mem-direct",
                "role": "change_relevant_to",
                "status": "archived",
                "confidence": 1.0,
            }
        ]

    def get_concept_bundle(self, *, repo_id: str, concept_ref: str):
        if repo_id != "repo-a" or concept_ref != "c-db":
            return None
        return {
            "concept": self._concept,
            "aliases": [],
            "claims": [
                ConceptClaim(
                    id="claim-archived",
                    repo_id="repo-a",
                    concept_id="c-db",
                    claim_type=ConceptClaimType.DEFINITION,
                    text="Archived concept definition.",
                    normalized_text="archived concept definition",
                    lifecycle=ConceptLifecycle(
                        status=ConceptLifecycleStatus.ARCHIVED,
                    ),
                )
            ],
            "relations": [],
            "anchors": [],
            "groundings": [],
            "memory_links": [],
            "evidence": [],
        }


class _NoFakeConcepts:
    def find_concepts_for_memory_ids(self, **kwargs):
        del kwargs
        return []

    def get_concept_bundle(self, *, repo_id: str, concept_ref: str):
        del repo_id, concept_ref
        return None


class _EmptyFakeReadPolicy:
    def list_structural_memory_relation_rows(self, **kwargs):
        del kwargs
        return []


class _StructuralFakeReadPolicy:
    def list_structural_memory_relation_rows(self, **kwargs):
        if kwargs["anchor_memory_id"] != "mem-direct":
            return []
        if "explained_by_change" not in set(kwargs["predicates"]):
            return []
        return [
            {
                "subject_memory_id": "mem-direct",
                "predicate": "explained_by_change",
                "object_memory_id": "mem-change",
                "visible_memory_ids": ("mem-direct", "mem-change"),
            }
        ]


class _FakeUow:
    def __init__(self) -> None:
        self.memories = _FakeMemories()
        self.concepts = _FakeConcepts()
        self.semantic_retrieval = _FakeSemanticRetrieval()
        self.keyword_retrieval = _FakeKeywordRetrieval()
        self.concept_semantic_retrieval = _FakeConceptSemanticRetrieval()
        self.concept_keyword_retrieval = _FakeConceptKeywordRetrieval()
        self.read_policy = _EmptyFakeReadPolicy()
        self.vector_search = _FakeVectorSearch()
