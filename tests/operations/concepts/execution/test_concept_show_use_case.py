"""Execution contracts for the concept-show use case."""

from collections.abc import Callable

from app.core.contracts.concepts import (
    ConceptAddRequest,
    ConceptShowRequest,
    ConceptUpdateRequest,
)
from app.core.ports.idgen import IIdGenerator
from app.core.use_cases.concepts.add import add_concepts
from app.core.use_cases.concepts.show import show_concept
from app.core.use_cases.concepts.update import update_concepts
from app.infrastructure.db.uow import PostgresUnitOfWork


class _SequenceIdGenerator(IIdGenerator):
    def __init__(self) -> None:
        self._next = 0

    def new_id(self) -> str:
        self._next += 1
        return f"concept-id-{self._next}"


def test_concept_show_should_return_dynamic_preview_concept(
    uow_factory: Callable[[], PostgresUnitOfWork],
) -> None:
    """concept show should represent a small Deposit Addresses graph."""

    _seed_deposit_addresses(uow_factory)

    with uow_factory() as uow:
        show = show_concept(
            ConceptShowRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "concept": "deposit-addresses",
                    "include": [
                        "claims",
                        "relations",
                        "groundings",
                        "memory_links",
                        "preview_concept",
                    ],
                }
            ),
            uow,
        )

    payload = show.data["concept"]
    assert payload["slug"] == "deposit-addresses"
    assert payload["preview_concept"]["name"] == "Deposit Addresses"
    assert payload["preview_concept"]["claim_count"] == 1
    assert payload["status_rollup"]["active"] == 2


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
            id_generator=_SequenceIdGenerator(),
        )
    with uow_factory() as uow:
        update_concepts(
            ConceptUpdateRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "add_relation",
                            "subject": "deposit-addresses",
                            "predicate": "contains",
                            "object": "deposit-lifecycle",
                            "evidence": [
                                {"kind": "manual", "note": "Seeded from planning."}
                            ],
                        },
                        {
                            "type": "add_claim",
                            "concept": "deposit-addresses",
                            "claim_type": "definition",
                            "text": "Relay-controlled EOAs users send funds to.",
                            "evidence": [
                                {"kind": "manual", "note": "Seeded from planning."}
                            ],
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
                                {
                                    "kind": "manual",
                                    "note": "Implementation starting point.",
                                }
                            ],
                        },
                    ],
                }
            ),
            uow,
            id_generator=_SequenceIdGenerator(),
        )
