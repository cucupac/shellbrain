"""Execution contracts for the concept endpoint use case."""

from collections.abc import Callable

from app.core.contracts.concepts import ConceptCommandRequest
from app.core.entities.memory import MemoryKind, MemoryScope
from app.core.use_cases.concepts.apply_concept_changes import execute_concept_command
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


def test_concept_apply_should_seed_deposit_addresses_canary_and_show_preview(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """concept apply/show should represent a small Deposit Addresses graph."""

    seed_memory(
        memory_id="refund-problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Refund problem.",
    )

    with uow_factory() as uow:
        result = execute_concept_command(_deposit_addresses_request(), uow)

    assert result.status == "ok"
    assert result.data["applied_count"] == 9
    assert len(fetch_rows(concepts)) == 4
    assert len(fetch_rows(concept_relations)) == 2
    assert len(fetch_rows(concept_claims)) == 1
    assert len(fetch_rows(anchors)) == 1
    assert len(fetch_rows(concept_groundings)) == 1
    assert len(fetch_rows(concept_memory_links)) == 1
    assert len(fetch_rows(concept_evidence)) == 5

    with uow_factory() as uow:
        show = execute_concept_command(
            ConceptCommandRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "mode": "show",
                    "concept": "deposit-addresses",
                    "include": ["claims", "relations", "groundings", "memory_links", "preview_concept"],
                }
            ),
            uow,
        )

    payload = show.data["concept"]
    assert payload["slug"] == "deposit-addresses"
    assert payload["preview_concept"]["name"] == "Deposit Addresses"
    assert payload["preview_concept"]["claim_count"] == 1
    assert payload["status_rollup"]["active"] == 2


def test_concept_apply_should_be_idempotent_for_natural_keys(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """re-applying the same concept payload should not duplicate natural-key records."""

    seed_memory(
        memory_id="refund-problem-1",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.PROBLEM,
        text_value="Refund problem.",
    )
    request = _deposit_addresses_request()

    with uow_factory() as uow:
        execute_concept_command(request, uow)
    with uow_factory() as uow:
        execute_concept_command(request, uow)

    assert len(fetch_rows(concepts)) == 4
    assert len(fetch_rows(concept_relations)) == 2
    assert len(fetch_rows(concept_claims)) == 1
    assert len(fetch_rows(anchors)) == 1
    assert len(fetch_rows(concept_groundings)) == 1
    assert len(fetch_rows(concept_memory_links)) == 1
    assert len(fetch_rows(concept_evidence)) == 5


def test_concept_apply_should_reject_invalid_relation_shapes(
    uow_factory: Callable[[], PostgresUnitOfWork],
) -> None:
    """relation shape validation should reject process precedence from non-process concepts."""

    request = ConceptCommandRequest.model_validate(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "mode": "apply",
            "actions": [
                {"type": "upsert_concept", "slug": "deposit-addresses", "name": "Deposit Addresses", "kind": "domain"},
                {"type": "upsert_concept", "slug": "refund-policy", "name": "Refund Policy", "kind": "rule"},
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
            execute_concept_command(request, uow)
        except ValueError as exc:
            assert "precedes requires process -> process" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Expected invalid relation shape to fail")


def _deposit_addresses_request() -> ConceptCommandRequest:
    return ConceptCommandRequest.model_validate(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "mode": "apply",
            "actions": [
                {
                    "type": "upsert_concept",
                    "slug": "deposit-addresses",
                    "name": "Deposit Addresses",
                    "kind": "domain",
                    "aliases": ["deposit address", "deposit-address feature"],
                },
                {"type": "upsert_concept", "slug": "deposit-lifecycle", "name": "Deposit Lifecycle", "kind": "process"},
                {"type": "upsert_concept", "slug": "refund-policy", "name": "Refund Policy", "kind": "rule"},
                {"type": "upsert_concept", "slug": "solver-eoa", "name": "Solver EOA", "kind": "entity"},
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
                    "anchor": {"kind": "file", "locator": {"path": "app/deposit_addresses.py"}},
                    "evidence": [{"kind": "manual", "note": "Implementation starting point."}],
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
