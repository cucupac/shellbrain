"""Unit coverage for deterministic graph-first recall packing."""

from __future__ import annotations

from dataclasses import replace

import pytest

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
    _bundle_signal_score,
    _new_candidate,
    _select_concepts,
    _select_final_memories,
    build_deterministic_graph_pack,
    source_items_from_graph_pack,
)
from app.core.use_cases.retrieval.read.request import MemoryReadRequest
from app.core.use_cases.retrieval.recall.request import MemoryRecallRequest
from app.core.use_cases.retrieval.read import execute_read_memory


def test_query_lanes_extract_identifiers_from_natural_language_query() -> None:
    """query lanes should preserve concrete identifiers from natural language."""

    request = _request(query='Debug `app/core/settings.py` "TimeoutError" SB-123 v1.2')

    lanes = _build_query_lanes(request)
    lane_queries = {lane.name: lane.query for lane in lanes}

    assert "app/core/settings.py" in lane_queries["identifiers"]
    assert "TimeoutError" in lane_queries["identifiers"]
    assert "SB-123" in lane_queries["identifiers"]
    assert "v1.2" in lane_queries["identifiers"]


def test_graph_pack_discovers_concepts_without_memory_links_and_pulls_graph_context() -> (
    None
):
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
    assert any(
        anchor["locator"] == "app/core/settings.py" for anchor in pack["anchors"]
    )
    assert "currentness" not in pack["concepts"][0]
    assert pack["concepts"][0]["freshness"]["stale"] == 1
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
    uow.concept_semantic_retrieval = _NoFakeConceptSemanticRetrieval()

    pack = build_deterministic_graph_pack(
        request=_request(query="TimeoutError in app/core/settings.py"),
        uow=uow,
    )

    assert pack["concepts"] == []
    memory_by_id = {memory["id"]: memory for memory in pack["memories"]}
    assert memory_by_id["mem-direct"]["currentness"] == "current"
    assert memory_by_id["mem-direct"]["link_roles"] == []
    assert memory_by_id["mem-direct"]["concept_refs"] == []
    assert pack["pack_trace"]["concept_candidates"]["candidate_count"] == 0
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


def _request(*, query: str) -> MemoryReadRequest:
    return MemoryReadRequest.model_validate(
        {
            "repo_id": "repo-a",
            "query": query,
            "limit": 24,
            "expand": {"concepts": {"max_auto": 6}},
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


def test_memory_and_concept_search_share_each_lane_embedding() -> None:
    uow = _FakeUow()
    queries = []

    class CountingVectorSearch(_FakeVectorSearch):
        def embed_query(self, query: str) -> list[float]:
            queries.append(query)
            return super().embed_query(query)

    uow.vector_search = CountingVectorSearch()
    pack = build_deterministic_graph_pack(
        request=_request(query="TimeoutError in app/core/settings.py"),
        uow=uow,
    )
    assert queries == [lane["query"] for lane in pack["query_lanes"]]


@pytest.mark.parametrize(
    "query, expect_broad",
    [
        ("migration locks", False),
        ("Migration   locks", False),
        (
            "migration locks after deployment with concurrent tasks across many worker processes",
            True,
        ),
    ],
)
def test_fallback_search_runs_only_for_a_new_query(
    query, expect_broad, monkeypatch
) -> None:
    uow = _FakeUow()
    queries = []
    memory_searches = []
    concept_searches = []
    monkeypatch.setattr(
        uow.vector_search, "embed_query", lambda query: queries.append(query) or [1.0]
    )
    monkeypatch.setattr(
        uow.semantic_retrieval,
        "query_semantic",
        lambda **kwargs: memory_searches.append(kwargs) or [],
    )
    monkeypatch.setattr(
        uow.concept_semantic_retrieval,
        "query_concepts_semantic",
        lambda **kwargs: concept_searches.append(kwargs) or [],
    )
    pack = build_deterministic_graph_pack(request=_request(query=query), uow=uow)
    assert len(queries) == len({query.casefold() for query in queries})
    assert queries == [lane["query"] for lane in pack["query_lanes"]]
    assert len(memory_searches) == len(concept_searches) == len(queries)
    assert (
        any(lane["lane"] == "broad_domain" for lane in pack["query_lanes"])
        == expect_broad
    )


@pytest.mark.parametrize("status", ["stale", "superseded", "wrong", "archived"])
def test_historical_facets_do_not_lower_active_concept_rank(
    status, monkeypatch
) -> None:
    uow = _FakeUow()
    request = _request(query="TimeoutError in app/core/settings.py")
    candidates = {"c-db": {"score": 1.0, "why": []}}
    before, _ = _select_concepts(
        request=request, concept_candidates=candidates, uow=uow
    )
    get_bundle = uow.concepts.get_concept_bundle

    def with_history(**kwargs):
        bundle = get_bundle(**kwargs)
        if bundle and kwargs["concept_ref"] == "c-db":
            for facet in ("claims", "relations", "groundings", "memory_links"):
                record = bundle[facet][0]
                bundle[facet].append(
                    replace(
                        record,
                        id=f"historical-{facet}",
                        lifecycle=ConceptLifecycle(
                            status=ConceptLifecycleStatus(status)
                        ),
                    )
                )
        return bundle

    monkeypatch.setattr(uow.concepts, "get_concept_bundle", with_history)
    after, _ = _select_concepts(request=request, concept_candidates=candidates, uow=uow)
    assert [entry["bundle"]["concept"].slug for entry in after] == ["db-admin"]
    assert after[0]["score"] == before[0]["score"]
    pack = build_deterministic_graph_pack(request=request, uow=uow)
    assert any(
        claim["id"] == "historical-claims" and claim["status"] == status
        for claim in pack["concepts"][0]["claims"]
    )
    assert any(
        claim["id"] == "claim-failure" and claim["currentness"] == "current"
        for claim in pack["concepts"][0]["claims"]
    )
    assert any(memory["id"] == "mem-warning" for memory in pack["memories"])


def test_archived_grounding_does_not_add_anchor_ranking_signal() -> None:
    bundle = _FakeConcepts().get_concept_bundle(repo_id="repo-a", concept_ref="c-db")
    for facet in ("claims", "relations", "groundings", "memory_links"):
        bundle[facet] = [
            replace(
                record,
                lifecycle=ConceptLifecycle(status=ConceptLifecycleStatus.ARCHIVED),
            )
            for record in bundle[facet]
        ]
    assert (
        _bundle_signal_score(
            bundle=bundle,
            query_terms=["TimeoutError"],
            identifiers=["app/core/settings.py"],
        )
        == 0.0
    )


def test_historical_link_does_not_label_memory_reached_through_active_link(
    monkeypatch,
) -> None:
    uow = _FakeUow()
    get_bundle = uow.concepts.get_concept_bundle

    def with_retired_link(**kwargs):
        bundle = get_bundle(**kwargs)
        if bundle and kwargs["concept_ref"] == "c-db":
            bundle["memory_links"].append(
                replace(
                    bundle["memory_links"][0],
                    id="old-link",
                    memory_id="mem-change-context",
                    lifecycle=ConceptLifecycle(status=ConceptLifecycleStatus.ARCHIVED),
                )
            )
        return bundle

    monkeypatch.setattr(uow.concepts, "get_concept_bundle", with_retired_link)
    pack = build_deterministic_graph_pack(
        request=_request(query="migration configuration"), uow=uow
    )
    memory = next(
        item for item in pack["memories"] if item["id"] == "mem-change-context"
    )
    assert memory["link_roles"] == ["change_relevant_to"]


def _candidates_for_groups(groups):
    candidates = {}
    for prefix, count, kind, why, lanes, roles in groups:
        for index in range(count):
            memory_id = f"{prefix}-{index:02}"
            candidate = _new_candidate(
                Memory(
                    id=MemoryId(memory_id),
                    repo_id=RepoId("repo-a"),
                    scope=MemoryScope.REPO,
                    kind=kind,
                    text=memory_id,
                )
            )
            candidate.update(
                score=1.0,
                why=set(why),
                matched_lanes=list(lanes),
                link_roles=set(roles),
            )
            candidates[memory_id] = candidate
    return candidates


def test_reserved_groups_share_one_total_budget() -> None:
    candidates = _candidates_for_groups(
        [
            ("trap", 3, MemoryKind.FAILED_TACTIC, [], [], []),
            ("change", 2, MemoryKind.CHANGE, [], [], []),
            ("fact", 1, MemoryKind.FACT, [], [], []),
            ("graph", 4, MemoryKind.SOLUTION, ["graph_linked_memory"], [], []),
            (
                "structural",
                4,
                MemoryKind.SOLUTION,
                ["structural_memory_relation"],
                [],
                [],
            ),
            ("direct", 12, MemoryKind.SOLUTION, [], ["original"], []),
        ]
    )
    request = _request(query="migration configuration")
    selected, trace = _select_final_memories(
        request=request, memory_candidates=candidates
    )
    ids = [item["memory"].id for item in selected]
    assert len(ids) == len(set(ids)) == 24
    assert ids[:6] == [
        "trap-00",
        "trap-01",
        "trap-02",
        "change-00",
        "change-01",
        "fact-00",
    ]
    assert trace["rejected_memory_count"] == 2
    assert len({item["memory_id"] for item in trace["rejected"]}) == 2
    reversed_selection, _ = _select_final_memories(
        request=request, memory_candidates=dict(reversed(list(candidates.items())))
    )
    assert [item["memory"].id for item in reversed_selection] == ids


def test_overlapping_reserved_groups_do_not_take_an_extra_slot() -> None:
    candidates = _candidates_for_groups(
        [
            ("trap", 3, MemoryKind.FACT, [], [], ["warns_about", "change_relevant_to"]),
            ("extra", 1, MemoryKind.FACT, [], [], []),
            ("direct", 30, MemoryKind.SOLUTION, [], ["original"], []),
        ]
    )
    selected, _ = _select_final_memories(
        request=_request(query="prior cases"), memory_candidates=candidates
    )
    ids = [item["memory"].id for item in selected]
    assert ids[:3] == ["trap-00", "trap-01", "trap-02"]
    assert ids[3:15] == [f"direct-{index:02}" for index in range(12)]
    assert len(ids) == 24


@pytest.mark.parametrize(
    "count, query, expected",
    [
        (0, "migration configuration", 0),
        (4, "migration configuration", 4),
        (30, "migration configuration", 10),
        (30, "prior cases", 24),
    ],
)
def test_fill_budget_preserves_problem_solution_policy(count, query, expected) -> None:
    candidates = _candidates_for_groups(
        [("case", count, MemoryKind.SOLUTION, [], [], [])]
    )
    selected, trace = _select_final_memories(
        request=_request(query=query), memory_candidates=candidates
    )
    assert len(selected) == expected
    assert trace["rejected_memory_count"] == count - expected


def test_retired_grounding_cannot_hide_current_anchor(monkeypatch) -> None:
    uow = _FakeUow()
    get_bundle = uow.concepts.get_concept_bundle

    def with_retired_grounding(**kwargs):
        bundle = get_bundle(**kwargs)
        if bundle and kwargs["concept_ref"] == "c-db":
            current = bundle["groundings"][0]
            bundle["groundings"].insert(
                0,
                replace(
                    current,
                    id="old-grounding",
                    lifecycle=ConceptLifecycle(status=ConceptLifecycleStatus.ARCHIVED),
                ),
            )
        return bundle

    monkeypatch.setattr(uow.concepts, "get_concept_bundle", with_retired_grounding)
    pack = build_deterministic_graph_pack(
        request=_request(query="migration configuration"),
        uow=uow,
    )
    assert len(pack["anchors"]) == 1
    assert pack["anchors"][0]["currentness"] == "current"
    assert any(item["id"] == "grounding:old-grounding" for item in pack["conflicts"])


def test_archived_link_cannot_discover_an_otherwise_active_concept(monkeypatch) -> None:
    uow = _FakeUow()
    uow.concept_semantic_retrieval = _NoFakeConceptSemanticRetrieval()
    monkeypatch.setattr(
        uow.concepts,
        "find_concepts_for_memory_ids",
        lambda **kwargs: [
            {
                "concept_id": "c-db",
                "memory_id": "mem-direct",
                "role": "warns_about",
                "status": "archived",
                "confidence": 1.0,
            }
        ],
    )
    pack = build_deterministic_graph_pack(
        request=_request(query="TimeoutError in app/core/settings.py"),
        uow=uow,
    )
    assert pack["concepts"] == []
    assert pack["pack_trace"]["concept_candidates"]["candidate_count"] == 0


@pytest.mark.parametrize(
    "query",
    [
        "TimeoutError in app/core/settings.py",
        "previous migration failure",
        "migration policy",
    ],
)
def test_learning_and_recall_select_same_evidence(query):
    recall = build_deterministic_graph_pack(
        request=MemoryRecallRequest(repo_id="repo-a", query=query), uow=_FakeUow()
    )
    read = execute_read_memory(_request(query=query), _FakeUow()).data["pack"]
    read_items = [
        item
        for section in ("direct", "explicit_related", "implicit_related")
        for item in read[section]
    ]
    assert {item["id"] for item in read_items} == {
        "mem-direct",
        "mem-warning",
        "mem-change",
        "mem-change-context",
    }
    assert {item["id"] for item in read_items} == {
        item["id"] for item in recall["memories"]
    }
    assert len(read_items) == len({item["id"] for item in read_items})
    assert read["concepts"]["items"] == recall["concepts"]
    assert read["conflicts"] == recall["conflicts"]
    assert any(item["type"] == "stale_claim" for item in read["conflicts"])


@pytest.mark.parametrize(
    "include_global,expected",
    [(False, {"mem-direct"}), (True, {"mem-direct", "mem-change-context"})],
)
def test_learning_filters_apply_to_graph_linked_memories(include_global, expected):
    uow = _FakeUow()
    memories = uow.memories._memories
    memories["mem-warning"] = replace(memories["mem-warning"], repo_id=RepoId("repo-b"))
    memories["mem-change-context"] = replace(
        memories["mem-change-context"],
        repo_id=RepoId("repo-b"),
        scope=MemoryScope.GLOBAL,
    )
    request = MemoryReadRequest(
        repo_id="repo-a",
        query="TimeoutError",
        include_global=include_global,
        kinds=[MemoryKind.FACT],
    )
    pack = build_deterministic_graph_pack(request=request, uow=uow)
    assert {item["id"] for item in pack["memories"]} == expected


@pytest.mark.parametrize("limit", [1, 2, 3])
def test_learning_limit_bounds_all_memory_sources(limit):
    request = MemoryReadRequest(repo_id="repo-a", query="TimeoutError", limit=limit)
    pack = build_deterministic_graph_pack(request=request, uow=_FakeUow())
    assert len(pack["memories"]) == limit
