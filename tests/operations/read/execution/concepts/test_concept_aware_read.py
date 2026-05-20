"""Concept-aware read execution contracts."""

from collections.abc import Callable

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine

from app.core.use_cases.concepts.add.request import ConceptAddRequest
from app.core.use_cases.concepts.update.request import ConceptUpdateRequest
from app.core.entities.concepts import ConceptLifecycleStatus
from app.core.entities.memories import MemoryKind, MemoryScope
from app.core.ports.system.idgen import IIdGenerator
from app.core.use_cases.concepts.add import add_concepts
from app.core.use_cases.concepts.update import update_concepts
from app.core.use_cases.retrieval.read import execute_read_memory
from app.core.use_cases.retrieval.read_concepts import append_concepts_to_pack
from app.infrastructure.db.runtime.models.concepts import (
    concept_embeddings,
    concept_memory_links,
    concepts,
)
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork
from tests.operations.read._execution_helpers import make_read_request


class _SequenceIdGenerator(IIdGenerator):
    def __init__(self, prefix: str = "concept-id") -> None:
        self._prefix = prefix
        self._next = 0

    def new_id(self) -> str:
        self._next += 1
        return f"{self._prefix}-{self._next}"


def test_read_should_include_concepts_linked_to_returned_memories(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    monkeypatch,
) -> None:
    """auto concept selection should use concept-memory links from returned memories."""

    seed_read_memory(
        memory_id="refund-problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Refund problem.",
    )
    _seed_deposit_addresses(uow_factory)
    _stub_pack(monkeypatch, direct_memory_ids=["refund-problem-1"])

    with uow_factory() as uow:
        result = execute_read_memory(
            make_read_request(repo_id="repo-a", query="refund failure"), uow
        )

    pack = result.data["pack"]
    assert [item["memory_id"] for item in pack["direct"]] == ["refund-problem-1"]
    assert pack["concepts"]["mode"] == "auto"
    assert pack["concepts"]["items"][0]["ref"] == "deposit-addresses"
    assert pack["concepts"]["items"][0]["orientation"].startswith(
        "Relay-controlled EOAs"
    )
    assert pack["concepts"]["items"][0]["status"] == "active"
    assert pack["concepts"]["items"][0]["created_at"]
    assert pack["concepts"]["items"][0]["updated_at"]
    assert pack["concepts"]["items"][0]["key_claims"][0]["observed_at"]
    assert pack["concepts"]["items"][0]["key_claims"][0]["created_at"]
    assert pack["concepts"]["items"][0]["why_matched"][0]["reason"] == "linked_memory"
    assert (
        pack["concepts"]["items"][0]["expand"][0]["read_payload"]["expand"]["concepts"][
            "mode"
        ]
        == "explicit"
    )


def test_read_should_include_concepts_matching_query_aliases(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    monkeypatch,
) -> None:
    """auto concept selection should use concept aliases when no memory link exists."""

    seed_read_memory(
        memory_id="refund-problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Refund problem.",
    )
    _seed_deposit_addresses(uow_factory)
    _stub_pack(monkeypatch, direct_memory_ids=[])

    with uow_factory() as uow:
        result = execute_read_memory(
            make_read_request(repo_id="repo-a", query="deposit address refund failure"),
            uow,
        )

    concept_item = result.data["pack"]["concepts"]["items"][0]
    assert concept_item["ref"] == "deposit-addresses"
    assert {"reason": "concept_keyword", "rank": 1} in concept_item["why_matched"]


def test_read_should_include_concepts_matching_semantic_concept_embeddings(
    uow_factory: Callable[[], PostgresUnitOfWork],
    integration_engine: Engine,
    monkeypatch,
) -> None:
    """auto concept selection should use concept embeddings independent of memory hits."""

    with uow_factory() as uow:
        add_concepts(
            ConceptAddRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "add_concept",
                            "slug": "semantic-only",
                            "name": "Unrelated Surface",
                            "kind": "domain",
                        }
                    ],
                }
            ),
            uow,
            id_generator=_SequenceIdGenerator(prefix="semantic-concept-id"),
        )
    with integration_engine.begin() as conn:
        conn.execute(
            insert(concept_embeddings).values(
                concept_id="semantic-concept-id-1",
                repo_id="repo-a",
                model="stub-v1",
                dim=4,
                vector=[1.0, 0.0, 0.0, 0.0],
                source_hash="semantic-source",
            )
        )
    _stub_pack(monkeypatch, direct_memory_ids=[])

    with uow_factory() as uow:
        result = execute_read_memory(
            make_read_request(repo_id="repo-a", query="opaque query terms"), uow
        )

    concept_item = result.data["pack"]["concepts"]["items"][0]
    assert concept_item["ref"] == "semantic-only"
    assert {"reason": "concept_semantic", "rank": 1} in concept_item["why_matched"]


def test_concept_keyword_corpus_should_include_anchors_and_exclude_inactive_concepts(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
) -> None:
    """concept keyword adapter should expose active aggregate concept text only."""

    seed_read_memory(
        memory_id="refund-problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Refund problem.",
    )
    _seed_deposit_addresses(uow_factory)
    with uow_factory() as uow:
        add_concepts(
            ConceptAddRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "add_concept",
                            "slug": "archived-concept",
                            "name": "Archived Concept",
                            "kind": "domain",
                            "status": "archived",
                            "aliases": ["archived alias"],
                        }
                    ],
                }
            ),
            uow,
            id_generator=_SequenceIdGenerator(prefix="archived-concept-id"),
        )

    with uow_factory() as uow:
        rows = uow.concept_keyword_retrieval.list_concept_keyword_corpus(
            repo_id="repo-a", query_terms=["deposit"], candidate_limit=10
        )

    rows_by_id = {row["concept_id"]: row for row in rows}
    assert "deposit-concept-id-1" in rows_by_id
    assert "app/deposit_addresses.py" in rows_by_id["deposit-concept-id-1"]["text"]
    assert "archived-concept-id-1" not in rows_by_id


def test_read_should_suppress_concepts_when_requested(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    monkeypatch,
) -> None:
    """mode=none should keep the concept section stable but empty."""

    seed_read_memory(
        memory_id="refund-problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Refund problem.",
    )
    _seed_deposit_addresses(uow_factory)
    _stub_pack(monkeypatch, direct_memory_ids=["refund-problem-1"])

    with uow_factory() as uow:
        result = execute_read_memory(
            make_read_request(
                repo_id="repo-a",
                query="refund failure",
                expand={"concepts": {"mode": "none"}},
            ),
            uow,
        )

    assert result.data["pack"]["concepts"] == {
        "mode": "none",
        "items": [],
        "missing_refs": [],
        "guidance": "Concept context suppressed by request.",
    }


def test_read_should_expand_explicit_concept_facets(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    monkeypatch,
) -> None:
    """explicit concept expansion should disclose requested facets through read."""

    seed_read_memory(
        memory_id="refund-problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Refund problem.",
    )
    _seed_deposit_addresses(uow_factory)
    _stub_pack(monkeypatch, direct_memory_ids=[])

    with uow_factory() as uow:
        result = execute_read_memory(
            make_read_request(
                repo_id="repo-a",
                query="deposit address refund failure",
                expand={
                    "concepts": {
                        "mode": "explicit",
                        "refs": ["deposit-addresses"],
                        "facets": [
                            "relations",
                            "groundings",
                            "memory_links",
                            "evidence",
                        ],
                    }
                },
            ),
            uow,
        )

    concept_item = result.data["pack"]["concepts"]["items"][0]
    assert concept_item["relations"][0]["predicate"] == "contains"
    assert concept_item["relations"][0]["created_at"]
    assert concept_item["relations"][0]["observed_at"]
    assert concept_item["groundings"][0]["anchor"]["locator"] == {
        "path": "app/deposit_addresses.py"
    }
    assert concept_item["groundings"][0]["created_at"]
    assert concept_item["groundings"][0]["anchor"]["created_at"]
    assert concept_item["memory_links"][0]["memory_id"] == "refund-problem-1"
    assert concept_item["memory_links"][0]["kind"] == "problem"
    assert concept_item["memory_links"][0]["memory_created_at"]
    assert concept_item["evidence"]
    assert concept_item["evidence"][0]["created_at"]


def test_read_should_penalize_stale_concept_links_in_auto_mode(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_read_memory: Callable[..., None],
    integration_engine: Engine,
    monkeypatch,
) -> None:
    """auto concept ranking should prefer active concept links over stale links."""

    seed_read_memory(
        memory_id="refund-problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Refund problem.",
    )
    _seed_deposit_addresses(uow_factory)
    _seed_refund_policy(uow_factory)
    with integration_engine.begin() as conn:
        deposit_concept_id = conn.execute(
            select(concepts.c.id).where(
                concepts.c.repo_id == "repo-a",
                concepts.c.slug == "deposit-addresses",
            )
        ).scalar_one()
        conn.execute(
            update(concept_memory_links)
            .where(concept_memory_links.c.concept_id == deposit_concept_id)
            .values(status=ConceptLifecycleStatus.STALE.value)
        )
    _stub_pack(monkeypatch, direct_memory_ids=["refund-problem-1"])

    with uow_factory() as uow:
        result = execute_read_memory(
            make_read_request(repo_id="repo-a", query="refund failure"), uow
        )

    assert [item["ref"] for item in result.data["pack"]["concepts"]["items"]][:2] == [
        "refund-policy",
        "deposit-addresses",
    ]


def test_read_should_reject_concept_links_missing_ranking_evidence() -> None:
    """auto concept ranking should not invent status or confidence for malformed links."""

    pack = {
        "direct": [{"memory_id": "memory-1"}],
        "explicit_related": [],
        "implicit_related": [],
    }

    with pytest.raises(
        ValueError, match="concept memory link is missing required status"
    ):
        append_concepts_to_pack(
            pack=pack,
            request=make_read_request(repo_id="repo-a", query="refund failure"),
            concepts=_MalformedConceptLinksRepo(),
            memories=object(),
        )


def _seed_deposit_addresses(uow_factory: Callable[[], PostgresUnitOfWork]) -> None:
    with uow_factory() as uow:
        add_concepts(
            ConceptAddRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "add_concept",
                            "slug": "deposit-addresses",
                            "name": "Deposit Addresses",
                            "kind": "domain",
                            "aliases": ["deposit address"],
                        },
                        {
                            "type": "add_concept",
                            "slug": "deposit-lifecycle",
                            "name": "Deposit Lifecycle",
                            "kind": "process",
                        },
                    ],
                }
            ),
            uow,
            id_generator=_SequenceIdGenerator(prefix="deposit-concept-id"),
        )
    with uow_factory() as uow:
        update_concepts(
            ConceptUpdateRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "add_claim",
                            "concept": "deposit-addresses",
                            "claim_type": "definition",
                            "text": "Relay-controlled EOAs users send funds to so Relay can execute bridge, swap, fill, or refund flows.",
                            "evidence": [
                                {
                                    "kind": "manual",
                                    "note": "Seeded for concept-aware read test.",
                                }
                            ],
                        },
                        {
                            "type": "add_relation",
                            "subject": "deposit-addresses",
                            "predicate": "contains",
                            "object": "deposit-lifecycle",
                            "evidence": [
                                {
                                    "kind": "manual",
                                    "note": "Seeded for concept-aware read test.",
                                }
                            ],
                        },
                        {
                            "type": "add_grounding",
                            "concept": "deposit-addresses",
                            "role": "implementation",
                            "anchor": {
                                "kind": "file",
                                "locator": {"path": "app/deposit_addresses.py"},
                            },
                            "evidence": [
                                {"kind": "manual", "note": "Implementation anchor."}
                            ],
                        },
                        {
                            "type": "link_memory",
                            "concept": "deposit-addresses",
                            "role": "example_of",
                            "memory_id": "refund-problem-1",
                            "evidence": [
                                {"kind": "manual", "note": "Related refund case."}
                            ],
                        },
                    ],
                }
            ),
            uow,
            id_generator=_SequenceIdGenerator(prefix="deposit-concept-update-id"),
        )


def _seed_refund_policy(uow_factory: Callable[[], PostgresUnitOfWork]) -> None:
    with uow_factory() as uow:
        add_concepts(
            ConceptAddRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "add_concept",
                            "slug": "refund-policy",
                            "name": "Refund Policy",
                            "kind": "rule",
                        },
                    ],
                }
            ),
            uow,
            id_generator=_SequenceIdGenerator(prefix="refund-concept-id"),
        )
    with uow_factory() as uow:
        update_concepts(
            ConceptUpdateRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "add_claim",
                            "concept": "refund-policy",
                            "claim_type": "definition",
                            "text": "Rules for returning funds when a deposit flow fails.",
                            "evidence": [
                                {
                                    "kind": "manual",
                                    "note": "Seeded for stale ranking test.",
                                }
                            ],
                        },
                        {
                            "type": "link_memory",
                            "concept": "refund-policy",
                            "role": "example_of",
                            "memory_id": "refund-problem-1",
                            "evidence": [
                                {"kind": "manual", "note": "Related refund case."}
                            ],
                        },
                    ],
                }
            ),
            uow,
            id_generator=_SequenceIdGenerator(prefix="refund-concept-update-id"),
        )


def _stub_pack(monkeypatch, *, direct_memory_ids: list[str]) -> None:
    pack = {
        "meta": {
            "mode": "targeted",
            "limit": 8,
            "counts": {
                "direct": len(direct_memory_ids),
                "explicit_related": 0,
                "implicit_related": 0,
            },
        },
        "direct": [
            {
                "memory_id": memory_id,
                "why_included": "direct_match",
                "priority": index,
                "kind": "problem",
                "text": "Refund problem.",
            }
            for index, memory_id in enumerate(direct_memory_ids, start=1)
        ],
        "explicit_related": [],
        "implicit_related": [],
    }
    monkeypatch.setattr(
        "app.core.use_cases.retrieval.read.build_context_pack",
        lambda *args, **kwargs: pack,
    )


class _MalformedConceptLinksRepo:
    """Concept repo stub that returns malformed auto-ranking evidence."""

    def find_concepts_for_memory_ids(self, *, repo_id: str, memory_ids):
        del repo_id, memory_ids
        return [
            {
                "concept_id": "concept-1",
                "role": "example_of",
                "confidence": 0.5,
            }
        ]
