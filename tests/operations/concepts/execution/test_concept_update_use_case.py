"""Execution contracts for the concept-update use case."""

from collections.abc import Callable

from app.core.contracts.concepts import ConceptAddRequest, ConceptUpdateRequest
from app.core.entities.memories import MemoryKind, MemoryScope
from app.core.ports.runtime.idgen import IIdGenerator
from app.core.use_cases.concepts.add import add_concepts
from app.core.use_cases.concepts.update import update_concepts
from app.infrastructure.db.models.concepts import (
    anchors,
    concept_claims,
    concept_evidence,
    concept_groundings,
    concept_memory_links,
    concept_relations,
    concepts,
)
from app.infrastructure.db.uow import PostgresUnitOfWork


class _SequenceIdGenerator(IIdGenerator):
    def __init__(self) -> None:
        self._next = 0

    def new_id(self) -> str:
        self._next += 1
        return f"concept-id-{self._next}"


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
    assert len(fetch_rows(concept_evidence)) == 5


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
    assert len(fetch_rows(concept_evidence)) == 5


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
