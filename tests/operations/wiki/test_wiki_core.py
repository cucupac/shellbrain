"""Core use-case coverage for Shellbrain Wiki."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.errors import DomainValidationError
from app.core.entities.concepts import (
    Anchor,
    AnchorKind,
    AnchorStatus,
    Concept,
    ConceptClaim,
    ConceptClaimType,
    ConceptEvidence,
    ConceptEvidenceKind,
    ConceptEvidenceTargetType,
    ConceptGrounding,
    ConceptGroundingRole,
    ConceptKind,
    ConceptLifecycle,
    ConceptMemoryLink,
    ConceptMemoryLinkRole,
    ConceptRelation,
    ConceptRelationPredicate,
    ConceptStatus,
)
from app.core.entities.evidence import (
    EvidenceDetail,
    EvidenceLinkedTarget,
    EvidenceLinkView,
    EvidenceRole,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceTarget,
    EvidenceTargetType,
)
from app.core.entities.memories import Memory, MemoryKind, MemoryLifecycleStatus, MemoryScope
from app.core.entities.repositories import RepositorySummary
from app.core.entities.wiki_summaries import WikiSummaryFreshness
from app.core.use_cases.wiki import (
    wiki_anchor_page,
    wiki_concept_facet,
    wiki_concept_page,
    wiki_home,
    wiki_index,
    wiki_memory_page,
    wiki_search,
)
from app.core.use_cases.wiki.request import (
    WikiAnchorRequest,
    WikiConceptFacetRequest,
    WikiConceptRequest,
    WikiIndexRequest,
    WikiMemoryRequest,
    WikiRepoRequest,
    WikiSearchRequest,
)


NOW = datetime(2026, 6, 5, tzinfo=timezone.utc)


def test_wiki_index_lists_repositories_and_marks_current() -> None:
    uow = _FakeUow()

    result = wiki_index(WikiIndexRequest(current_repo_id="repo"), uow)

    assert [item.repo_id for item in result.repositories] == ["other-repo", "repo"]
    assert result.repositories[0].popularity_score == 11
    assert result.repositories[1].is_current


def test_wiki_home_groups_active_concepts_by_kind() -> None:
    uow = _FakeUow()

    result = wiki_home(WikiRepoRequest(repo_id="repo", now=NOW), uow)

    groups = {group.kind: [item.slug for item in group.concepts] for group in result.groups}
    assert groups == {
        "process": ["recall", "build-context"],
        "rule": ["evidence-discipline"],
    }
    assert (
        result.groups[0].concepts[0].definition
        == "Recall returns a compact read-only brief."
    )
    assert result.groups[0].concepts[0].memory_count == 1
    assert result.groups[0].concepts[0].popularity_score == 3
    assert result.summary is not None
    assert result.summary.freshness == WikiSummaryFreshness.MISSING


def test_wiki_concept_page_and_facets_show_typed_records() -> None:
    uow = _FakeUow()

    page = wiki_concept_page(
        WikiConceptRequest(repo_id="repo", now=NOW, concept_ref="recall"), uow
    )
    relations = wiki_concept_facet(
        WikiConceptFacetRequest(
            repo_id="repo", now=NOW, concept_ref="recall", facet="relations"
        ),
        uow,
    )
    memory_links = wiki_concept_facet(
        WikiConceptFacetRequest(
            repo_id="repo", now=NOW, concept_ref="recall", facet="memory-links"
        ),
        uow,
    )

    assert page.definition == "Recall returns a compact read-only brief."
    assert page.evidence_total == 1
    assert page.status_rollup == {"active": 4}
    assert page.summary is not None
    assert page.summary.freshness == WikiSummaryFreshness.MISSING
    assert relations.relations[0].predicate == "depends_on"
    assert relations.relations[0].object.slug == "build-context"
    assert memory_links.memory_links[0].memory_kind == "solution"


def test_wiki_memory_page_shows_links_neighbors_and_evidence() -> None:
    uow = _FakeUow()

    result = wiki_memory_page(
        WikiMemoryRequest(
            repo_id="repo",
            now=NOW,
            memory_id="mem-solution",
            include_global=True,
        ),
        uow,
    )

    assert result.kind == "solution"
    assert result.concept_links[0].concept.slug == "recall"
    assert result.neighbors[0].memory_id == "mem-problem"
    assert result.evidence[0].source_kind == "manual"


def test_wiki_anchor_page_returns_explicit_not_found() -> None:
    with pytest.raises(DomainValidationError) as excinfo:
        wiki_anchor_page(
            WikiAnchorRequest(repo_id="repo", now=NOW, anchor_id="missing"),
            _FakeUow(),
        )

    assert excinfo.value.errors[0].field == "anchor_id"
    assert excinfo.value.errors[0].code.value == "not_found"


def test_wiki_search_is_keyword_only_and_blank_query_returns_no_hits() -> None:
    uow = _FakeUow()

    blank = wiki_search(
        WikiSearchRequest(repo_id="repo", now=NOW, query="", include_global=True), uow
    )
    result = wiki_search(
        WikiSearchRequest(
            repo_id="repo", now=NOW, query="recall", include_global=True
        ),
        uow,
    )

    assert blank.hits == ()
    assert [hit.record_type for hit in result.hits] == ["concept", "memory"]


class _FakeUow:
    def __init__(self) -> None:
        self.repository_index = _FakeRepositoryIndexRepo()
        self.concepts = _FakeConceptsRepo()
        self.memories = _FakeMemoriesRepo()
        self.evidence = _FakeEvidenceRepo()
        self.read_policy = _FakeReadPolicyRepo()
        self.keyword_retrieval = _FakeKeywordRetrievalRepo()
        self.concept_keyword_retrieval = _FakeConceptKeywordRetrievalRepo()
        self.wiki_summaries = _FakeWikiSummaryRepo()


class _FakeRepositoryIndexRepo:
    def list_repositories(self):
        return [
            RepositorySummary(
                repo_id="repo",
                repo_root="/repo",
                concept_count=2,
                memory_count=2,
                evidence_count=1,
                last_seen_at=NOW.isoformat(),
            ),
            RepositorySummary(
                repo_id="other-repo",
                repo_root="/other",
                concept_count=1,
                memory_count=3,
                evidence_count=7,
                last_seen_at=None,
            ),
        ]


class _FakeConceptsRepo:
    def __init__(self) -> None:
        self._concepts = {
            "concept-recall": _concept("concept-recall", "recall", "Recall", "process"),
            "concept-build": _concept(
                "concept-build", "build-context", "Build Context", "process"
            ),
            "concept-rule": _concept(
                "concept-rule", "evidence-discipline", "Evidence Discipline", "rule"
            ),
        }
        self._bundle = _concept_bundle(self._concepts)

    def list_concepts(self, *, repo_id: str, statuses):
        assert repo_id == "repo"
        return [
            self._concepts["concept-build"],
            self._concepts["concept-recall"],
            self._concepts["concept-rule"],
        ]

    def get_concept_bundle(self, *, repo_id: str, concept_ref: str, **_kwargs):
        assert repo_id == "repo"
        if concept_ref not in {"recall", "concept-recall"}:
            return None
        return self._bundle

    def list_concepts_by_ids(self, *, repo_id: str, concept_ids):
        assert repo_id == "repo"
        return [self._concepts[concept_id] for concept_id in concept_ids]

    def find_concepts_for_memory_ids(self, *, repo_id: str, memory_ids):
        assert repo_id == "repo"
        if "mem-solution" not in memory_ids:
            return []
        return [
            {
                "concept_id": "concept-recall",
                "memory_id": "mem-solution",
                "role": "solution_for",
                "status": "active",
                "confidence": 0.8,
            }
        ]

    def get_anchor(self, *, repo_id: str, anchor_id: str):
        assert repo_id == "repo"
        if anchor_id != "anchor-recall":
            return None
        return _anchor()

    def find_concepts_for_anchor_ids(self, *, repo_id: str, anchor_ids):
        assert repo_id == "repo"
        if "anchor-recall" not in anchor_ids:
            return []
        return [
            {
                "concept_id": "concept-recall",
                "slug": "recall",
                "name": "Recall",
                "kind": "process",
                "grounding_id": "grounding-recall",
                "anchor_id": "anchor-recall",
                "role": "implementation",
                "status": "active",
                "confidence": 0.9,
            }
        ]


class _FakeMemoriesRepo:
    def __init__(self) -> None:
        self._memories = {
            "mem-solution": _memory("mem-solution", "solution", "Recall used build context."),
            "mem-problem": _memory("mem-problem", "problem", "Recall needed context."),
        }

    def get(self, memory_id: str):
        return self._memories.get(memory_id)

    def list_by_ids(self, ids):
        return [self._memories[memory_id] for memory_id in ids if memory_id in self._memories]

    def list_recent(self, *, repo_id: str, statuses, limit: int):
        assert repo_id == "repo"
        return list(self._memories.values())[:limit]


class _FakeWikiSummaryRepo:
    def get(self, target):
        return None

    def acquire_refresh(self, **_kwargs):
        return True

    def record_success(self, **_kwargs):
        return None

    def record_failure(self, **_kwargs):
        return None

    def list_existing_targets(self, *, repo_ids):
        return ()


class _FakeEvidenceRepo:
    def resolve_evidence(self, *, repo_id: str, targets):
        assert repo_id == "repo"
        return [
            EvidenceLinkView(
                target=targets[0],
                source=EvidenceSource(
                    source_kind=EvidenceSourceKind.MANUAL, note="verified manually"
                ),
                role=EvidenceRole.SUPPORTS,
                evidence_id="evidence-1",
                created_at=NOW,
            )
        ]

    def get_evidence_detail(self, *, repo_id: str, evidence_id: str):
        assert repo_id == "repo"
        if evidence_id != "evidence-1":
            return None
        return EvidenceDetail(
            id=evidence_id,
            repo_id=repo_id,
            source=EvidenceSource(
                source_kind=EvidenceSourceKind.MANUAL, note="verified manually"
            ),
            linked_targets=(
                EvidenceLinkedTarget(
                    link_id="link-1",
                    target=EvidenceTarget(
                        target_type=EvidenceTargetType.MEMORY,
                        target_id="mem-solution",
                    ),
                    role=EvidenceRole.SUPPORTS,
                    created_at=NOW,
                ),
            ),
            created_at=NOW,
        )


class _FakeReadPolicyRepo:
    def list_structural_memory_relation_rows(self, **_kwargs):
        return [
            {
                "subject_memory_id": "mem-problem",
                "predicate": "solved_by",
                "object_memory_id": "mem-solution",
                "visible_memory_ids": ("mem-problem", "mem-solution"),
            }
        ]

    def list_association_edge_rows(self, **_kwargs):
        return []


class _FakeConceptKeywordRetrievalRepo:
    def list_concept_keyword_corpus(self, **_kwargs):
        return [{"concept_id": "concept-recall", "text": "recall process brief"}]


class _FakeKeywordRetrievalRepo:
    def list_keyword_corpus(self, **_kwargs):
        return [
            {
                "memory_id": "mem-solution",
                "text": "recall used build context",
                "status": "active",
            }
        ]


def _concept(concept_id: str, slug: str, name: str, kind: str) -> Concept:
    return Concept(
        id=concept_id,
        repo_id="repo",
        slug=slug,
        name=name,
        kind=ConceptKind(kind),
        status=ConceptStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )


def _concept_bundle(concepts: dict[str, Concept]) -> dict[str, object]:
    claim = ConceptClaim(
        id="claim-definition",
        repo_id="repo",
        concept_id="concept-recall",
        claim_type=ConceptClaimType.DEFINITION,
        text="Recall returns a compact read-only brief.",
        normalized_text="recall returns a compact read-only brief",
        lifecycle=ConceptLifecycle(confidence=0.9),
        created_at=NOW,
        updated_at=NOW,
    )
    relation = ConceptRelation(
        id="relation-build",
        repo_id="repo",
        subject_concept_id="concept-recall",
        predicate=ConceptRelationPredicate.DEPENDS_ON,
        object_concept_id="concept-build",
        lifecycle=ConceptLifecycle(confidence=0.8),
        created_at=NOW,
        updated_at=NOW,
    )
    grounding = ConceptGrounding(
        id="grounding-recall",
        repo_id="repo",
        concept_id="concept-recall",
        role=ConceptGroundingRole.IMPLEMENTATION,
        anchor_id="anchor-recall",
        lifecycle=ConceptLifecycle(confidence=0.8),
        created_at=NOW,
        updated_at=NOW,
    )
    memory_link = ConceptMemoryLink(
        id="memory-link-recall",
        repo_id="repo",
        concept_id="concept-recall",
        role=ConceptMemoryLinkRole.SOLUTION_FOR,
        memory_id="mem-solution",
        lifecycle=ConceptLifecycle(confidence=0.8),
        created_at=NOW,
        updated_at=NOW,
    )
    return {
        "concept": concepts["concept-recall"],
        "aliases": [],
        "relations": [relation],
        "claims": [claim],
        "groundings": [grounding],
        "memory_links": [memory_link],
        "lifecycle_events": [],
        "anchors": [_anchor()],
        "evidence": [
            ConceptEvidence(
                id="evidence-link-1",
                repo_id="repo",
                target_type=ConceptEvidenceTargetType.CLAIM,
                target_id="claim-definition",
                evidence_kind=ConceptEvidenceKind.MANUAL,
                note="verified manually",
                evidence_id="evidence-1",
                created_at=NOW,
            )
        ],
    }


def _anchor() -> Anchor:
    return Anchor(
        id="anchor-recall",
        repo_id="repo",
        kind=AnchorKind.FILE,
        locator_json={"path": "app/core/use_cases/retrieval/recall/execute.py"},
        canonical_locator_hash="hash",
        status=AnchorStatus.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
    )


def _memory(memory_id: str, kind: str, text: str) -> Memory:
    return Memory(
        id=memory_id,
        repo_id="repo",
        scope=MemoryScope.REPO,
        kind=MemoryKind(kind),
        text=text,
        created_at=NOW,
        status=MemoryLifecycleStatus.ACTIVE,
    )
