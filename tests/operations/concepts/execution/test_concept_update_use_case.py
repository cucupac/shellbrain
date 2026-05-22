"""Execution contracts for the concept-update use case."""

from collections.abc import Callable
from datetime import datetime, timezone

from app.core.use_cases.concepts.add.request import ConceptAddRequest
from app.core.use_cases.concepts.update.request import ConceptUpdateRequest
from app.core.entities.memories import MemoryKind, MemoryScope
from app.core.ports.embeddings.provider import IEmbeddingProvider
from app.core.ports.system.clock import IClock
from app.core.ports.system.idgen import IIdGenerator
from app.core.use_cases.concepts.add import add_concepts
from app.core.use_cases.concepts.update import update_concepts
from app.infrastructure.db.runtime.models.concepts import (
    anchors,
    concept_claims,
    concept_embeddings,
    concept_groundings,
    concept_lifecycle_events,
    concept_memory_links,
    concept_relations,
    concepts,
)
from app.infrastructure.db.runtime.models.evidence import evidence_links
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork


class _SequenceIdGenerator(IIdGenerator):
    def __init__(self) -> None:
        self._next = 0

    def new_id(self) -> str:
        self._next += 1
        return f"concept-id-{self._next}"


class _FixedClock(IClock):
    def now(self) -> datetime:
        return datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def test_concept_update_should_attach_deposit_addresses_graph_records(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """concept update should add truth-bearing graph records for existing concepts."""

    _seed_deposit_concepts(uow_factory)
    seed_memory(
        memory_id="refund-problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Refund problem.",
    )

    with uow_factory() as uow:
        result = update_concepts(
            _deposit_graph_request(), uow, id_generator=_SequenceIdGenerator()
        )
    assert result.data["updated_count"] == 5
    assert len(fetch_rows(concepts)) == 4
    assert len(fetch_rows(concept_relations)) == 2
    assert len(fetch_rows(concept_claims)) == 1
    assert len(fetch_rows(anchors)) == 1
    assert len(fetch_rows(concept_groundings)) == 1
    assert len(fetch_rows(concept_memory_links)) == 1
    assert len(fetch_rows(evidence_links)) == 5


def test_concept_update_should_recompute_embeddings_for_touched_concepts(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """concept update should embed concepts touched by graph mutations."""

    _seed_deposit_concepts(uow_factory)
    seed_memory(
        memory_id="refund-problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Refund problem.",
    )

    with uow_factory() as uow:
        update_concepts(
            _deposit_graph_request(),
            uow,
            id_generator=_SequenceIdGenerator(),
            embedding_provider=stub_embedding_provider,
            embedding_model="stub-v1",
        )

    rows = fetch_rows(concept_embeddings)
    assert {row["concept_id"] for row in rows} == {
        "concept-id-1",
        "concept-id-2",
        "concept-id-3",
    }
    assert {row["model"] for row in rows} == {"stub-v1"}
    assert {row["dim"] for row in rows} == {4}


def test_concept_update_should_be_idempotent_for_natural_keys(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """re-applying the same concept update payload should not duplicate natural-key records."""

    _seed_deposit_concepts(uow_factory)
    seed_memory(
        memory_id="refund-problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Refund problem.",
    )
    request = _deposit_graph_request()

    with uow_factory() as uow:
        update_concepts(request, uow, id_generator=_SequenceIdGenerator())
    with uow_factory() as uow:
        update_concepts(request, uow, id_generator=_SequenceIdGenerator())

    assert len(fetch_rows(concepts)) == 4
    assert len(fetch_rows(concept_relations)) == 2
    assert len(fetch_rows(concept_claims)) == 1
    assert len(fetch_rows(anchors)) == 1
    assert len(fetch_rows(concept_groundings)) == 1
    assert len(fetch_rows(concept_memory_links)) == 1
    assert len(fetch_rows(evidence_links)) == 5


def test_concept_update_should_update_lifecycle_for_all_truth_record_types(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """concept update should audit lifecycle changes for all truth-bearing records."""

    _seed_deposit_concepts(uow_factory)
    seed_memory(
        memory_id="refund-problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Refund problem.",
    )
    with uow_factory() as uow:
        update_concepts(
            _deposit_graph_request(), uow, id_generator=_SequenceIdGenerator()
        )

    relation_id = fetch_rows(concept_relations)[0]["id"]
    claim_id = fetch_rows(concept_claims)[0]["id"]
    grounding_id = fetch_rows(concept_groundings)[0]["id"]
    memory_link_id = fetch_rows(concept_memory_links)[0]["id"]

    request = ConceptUpdateRequest.model_validate(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "update_lifecycle",
                    "target_type": "relation",
                    "target_id": relation_id,
                    "status": "stale",
                    "rationale": "Relation is no longer current.",
                    "actor": "manual",
                    "evidence": [{"kind": "manual", "note": "Reviewed relation."}],
                },
                {
                    "type": "update_lifecycle",
                    "target_type": "claim",
                    "target_id": claim_id,
                    "status": "wrong",
                    "rationale": "Claim is contradicted by implementation.",
                    "actor": "manual",
                    "confidence": 0.1,
                    "evidence": [{"kind": "manual", "note": "Reviewed claim."}],
                },
                {
                    "type": "update_lifecycle",
                    "target_type": "grounding",
                    "target_id": grounding_id,
                    "status": "archived",
                    "rationale": "Grounding is retired from normal use.",
                    "actor": "manual",
                    "evidence": [{"kind": "manual", "note": "Reviewed grounding."}],
                },
                {
                    "type": "update_lifecycle",
                    "target_type": "memory_link",
                    "target_id": memory_link_id,
                    "status": "maybe_stale",
                    "rationale": "Link may be outdated.",
                    "actor": "manual",
                    "evidence": [{"kind": "manual", "note": "Reviewed link."}],
                },
            ],
        }
    )

    with uow_factory() as uow:
        result = update_concepts(
            request, uow, id_generator=_SequenceIdGenerator(), clock=_FixedClock()
        )

    assert result.data["updated_count"] == 4
    assert fetch_rows(concept_relations, concept_relations.c.id == relation_id)[0][
        "status"
    ] == "stale"
    claim = fetch_rows(concept_claims, concept_claims.c.id == claim_id)[0]
    assert claim["status"] == "wrong"
    assert claim["confidence"] == 0.1
    assert claim["invalidated_at"] is not None
    assert claim["updated_by"] == "manual"
    assert fetch_rows(concept_groundings, concept_groundings.c.id == grounding_id)[0][
        "status"
    ] == "archived"
    assert fetch_rows(concept_memory_links, concept_memory_links.c.id == memory_link_id)[
        0
    ]["status"] == "maybe_stale"

    events = fetch_rows(concept_lifecycle_events)
    assert len(events) == 4
    assert {event["target_type"] for event in events} == {
        "relation",
        "claim",
        "grounding",
        "memory_link",
    }
    assert {event["from_status"] for event in events} == {"active"}
    assert len(
        fetch_rows(
            evidence_links,
            evidence_links.c.target_type == "concept_lifecycle_event",
        )
    ) == 4


def test_concept_update_should_require_same_type_supersession_target(
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """superseded lifecycle updates should point at another same-type record."""

    _seed_deposit_concepts(uow_factory)
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
                            "text": "Old claim.",
                            "evidence": [{"kind": "manual", "note": "Old."}],
                        },
                        {
                            "type": "add_claim",
                            "concept": "deposit-addresses",
                            "claim_type": "definition",
                            "text": "New claim.",
                            "evidence": [{"kind": "manual", "note": "New."}],
                        },
                    ],
                }
            ),
            uow,
            id_generator=_SequenceIdGenerator(),
            clock=_FixedClock(),
        )

    claims = sorted(fetch_rows(concept_claims), key=lambda row: str(row["text"]))
    new_claim_id = claims[0]["id"]
    old_claim_id = claims[1]["id"]

    with uow_factory() as uow:
        update_concepts(
            ConceptUpdateRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "update_lifecycle",
                            "target_type": "claim",
                            "target_id": old_claim_id,
                            "status": "superseded",
                            "superseded_by_id": new_claim_id,
                            "rationale": "New claim replaces the old claim.",
                            "actor": "manual",
                            "evidence": [{"kind": "manual", "note": "Reviewed."}],
                        },
                    ],
                }
            ),
            uow,
            id_generator=_SequenceIdGenerator(),
            clock=_FixedClock(),
        )

    old_claim = fetch_rows(concept_claims, concept_claims.c.id == old_claim_id)[0]
    assert old_claim["status"] == "superseded"
    assert old_claim["superseded_by_id"] == new_claim_id
    assert old_claim["invalidated_at"] is not None

    with uow_factory() as uow:
        try:
            update_concepts(
                ConceptUpdateRequest.model_validate(
                    {
                        "schema_version": "concept.v1",
                        "repo_id": "repo-a",
                        "actions": [
                            {
                                "type": "update_lifecycle",
                                "target_type": "claim",
                                "target_id": new_claim_id,
                                "status": "superseded",
                                "superseded_by_id": new_claim_id,
                                "rationale": "Self supersession is invalid.",
                                "actor": "manual",
                                "evidence": [
                                    {"kind": "manual", "note": "Reviewed self."}
                                ],
                            },
                        ],
                    }
                ),
                uow,
                id_generator=_SequenceIdGenerator(),
                clock=_FixedClock(),
            )
        except ValueError as exc:
            assert "superseded_by_id cannot reference" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Expected self supersession to fail")


def test_concept_update_should_clear_invalidated_at_when_record_becomes_active(
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """active lifecycle updates should make invalidation metadata false no longer."""

    _seed_deposit_concepts(uow_factory)
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
                            "text": "Claim to invalidate and restore.",
                            "evidence": [{"kind": "manual", "note": "Seed."}],
                        }
                    ],
                }
            ),
            uow,
            id_generator=_SequenceIdGenerator(),
        )

    claim_id = fetch_rows(concept_claims)[0]["id"]
    with uow_factory() as uow:
        update_concepts(
            ConceptUpdateRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "update_lifecycle",
                            "target_type": "claim",
                            "target_id": claim_id,
                            "status": "wrong",
                            "rationale": "Temporarily invalidate.",
                            "actor": "manual",
                            "evidence": [{"kind": "manual", "note": "Wrong."}],
                        },
                        {
                            "type": "update_lifecycle",
                            "target_type": "claim",
                            "target_id": claim_id,
                            "status": "active",
                            "rationale": "Revalidated with evidence.",
                            "actor": "manual",
                            "evidence": [{"kind": "manual", "note": "Active."}],
                        },
                    ],
                }
            ),
            uow,
            id_generator=_SequenceIdGenerator(),
            clock=_FixedClock(),
        )

    claim = fetch_rows(concept_claims, concept_claims.c.id == claim_id)[0]
    assert claim["status"] == "active"
    assert claim["invalidated_at"] is None
    assert claim["validated_at"] is not None


def test_concept_update_should_reject_invalid_relation_shapes(
    uow_factory: Callable[[], PostgresUnitOfWork],
) -> None:
    """relation shape validation should reject process precedence from non-process concepts."""

    _seed_invalid_relation_concepts(uow_factory)
    request = ConceptUpdateRequest.model_validate(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "add_relation",
                    "subject": "deposit-addresses",
                    "predicate": "precedes",
                    "object": "refund-policy",
                    "evidence": [{"kind": "manual", "note": "Invalid relation."}],
                },
            ],
        }
    )

    with uow_factory() as uow:
        try:
            update_concepts(request, uow, id_generator=_SequenceIdGenerator())
        except ValueError as exc:
            assert "precedes requires process -> process" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Expected invalid relation shape to fail")


def test_concept_update_should_fail_if_concept_is_missing(
    uow_factory: Callable[[], PostgresUnitOfWork],
) -> None:
    """concept update should not create missing concepts."""

    request = ConceptUpdateRequest.model_validate(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "add_claim",
                    "concept": "deposit-addresses",
                    "claim_type": "definition",
                    "text": "Missing concept.",
                    "evidence": [{"kind": "manual", "note": "Missing concept."}],
                }
            ],
        }
    )

    with uow_factory() as uow:
        try:
            update_concepts(request, uow, id_generator=_SequenceIdGenerator())
        except ValueError as exc:
            assert "Concept not found: deposit-addresses" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Expected missing concept update to fail")


def _seed_deposit_concepts(uow_factory: Callable[[], PostgresUnitOfWork]) -> None:
    with uow_factory() as uow:
        add_concepts(
            _deposit_concepts_request(), uow, id_generator=_SequenceIdGenerator()
        )


def _seed_invalid_relation_concepts(
    uow_factory: Callable[[], PostgresUnitOfWork],
) -> None:
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
                        },
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
            id_generator=_SequenceIdGenerator(),
        )


def _deposit_concepts_request() -> ConceptAddRequest:
    return ConceptAddRequest.model_validate(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "add_concept",
                    "slug": "deposit-addresses",
                    "name": "Deposit Addresses",
                    "kind": "domain",
                    "aliases": ["deposit address", "deposit-address feature"],
                },
                {
                    "type": "add_concept",
                    "slug": "deposit-lifecycle",
                    "name": "Deposit Lifecycle",
                    "kind": "process",
                },
                {
                    "type": "add_concept",
                    "slug": "refund-policy",
                    "name": "Refund Policy",
                    "kind": "rule",
                },
                {
                    "type": "add_concept",
                    "slug": "solver-eoa",
                    "name": "Solver EOA",
                    "kind": "entity",
                },
            ],
        }
    )


def _deposit_graph_request() -> ConceptUpdateRequest:
    return ConceptUpdateRequest.model_validate(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "add_relation",
                    "subject": "deposit-addresses",
                    "predicate": "contains",
                    "object": "deposit-lifecycle",
                    "evidence": [{"kind": "manual", "note": "Seeded from planning."}],
                },
                {
                    "type": "add_relation",
                    "subject": "refund-policy",
                    "predicate": "constrains",
                    "object": "deposit-lifecycle",
                    "evidence": [{"kind": "manual", "note": "Seeded from planning."}],
                },
                {
                    "type": "add_claim",
                    "concept": "deposit-addresses",
                    "claim_type": "definition",
                    "text": "Relay-controlled EOAs users send funds to so Relay can execute bridge, swap, fill, or refund flows.",
                    "evidence": [{"kind": "manual", "note": "Seeded from planning."}],
                },
                {
                    "type": "add_grounding",
                    "concept": "deposit-lifecycle",
                    "role": "implementation",
                    "anchor": {
                        "kind": "file",
                        "locator": {"path": "app/deposit_addresses.py"},
                    },
                    "evidence": [
                        {"kind": "manual", "note": "Implementation starting point."}
                    ],
                },
                {
                    "type": "link_memory",
                    "concept": "refund-policy",
                    "role": "example_of",
                    "memory_id": "refund-problem-1",
                    "evidence": [{"kind": "manual", "note": "Canary case link."}],
                },
            ],
        }
    )
