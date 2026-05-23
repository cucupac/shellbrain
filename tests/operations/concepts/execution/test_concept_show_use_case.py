"""Execution contracts for the concept-show use case."""

from collections.abc import Callable
from datetime import datetime, timezone

from app.core.use_cases.concepts.add.request import ConceptAddRequest
from app.core.use_cases.concepts.show.request import ConceptShowRequest
from app.core.use_cases.concepts.update.request import ConceptUpdateRequest
from app.core.entities.memories import MemoryKind, MemoryScope
from app.core.ports.system.clock import IClock
from app.core.ports.system.idgen import IIdGenerator
from app.core.use_cases.concepts.add import add_concepts
from app.core.use_cases.concepts.show import show_concept
from app.core.use_cases.concepts.update import update_concepts
from app.infrastructure.db.runtime.models.concepts import concept_claims
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
    assert payload["created_at"]
    assert payload["updated_at"]
    assert payload["claims"][0]["created_at"]
    assert payload["claims"][0]["observed_at"]
    assert payload["relations"][0]["created_at"]
    assert payload["relations"][0]["observed_at"]
    assert payload["preview_concept"]["name"] == "Deposit Addresses"
    assert payload["preview_concept"]["claim_count"] == 1
    assert payload["status_rollup"]["active"] == 2


def test_concept_show_should_include_lifecycle_events_for_included_records(
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """concept show should expose auditable lifecycle history when requested."""

    _seed_deposit_addresses(uow_factory)
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
                            "rationale": "Claim contradicted by implementation.",
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

    with uow_factory() as uow:
        show = show_concept(
            ConceptShowRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "concept": "deposit-addresses",
                    "include": ["claims", "lifecycle_events"],
                }
            ),
            uow,
        )

    payload = show.data["concept"]
    assert payload["claims"][0]["status"] == "wrong"
    assert payload["claims"][0]["invalidated_at"]
    assert payload["claims"][0]["updated_by"] == "manual"
    assert payload["lifecycle_events"] == [
        {
            "id": "concept-id-1",
            "target_type": "claim",
            "target_id": claim_id,
            "from_status": "active",
            "to_status": "wrong",
            "rationale": "Claim contradicted by implementation.",
            "actor": "manual",
            "superseded_by_id": None,
            "created_at": payload["lifecycle_events"][0]["created_at"],
            "evidence_count": 1,
        }
    ]


def test_concept_show_should_surface_current_memory_link_roles(
    uow_factory: Callable[[], PostgresUnitOfWork],
    seed_memory: Callable[..., object],
) -> None:
    """concept show should expose the current bridge vocabulary."""

    _seed_deposit_addresses(uow_factory)
    seed_memory(
        memory_id="deposit-warning-memory",
        repo_id="repo-a",
        scope=MemoryScope.REPO,
        kind=MemoryKind.FACT,
        text_value="Deposit address cache misses can mislead retries.",
    )
    with uow_factory() as uow:
        update_concepts(
            ConceptUpdateRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "actions": [
                        {
                            "type": "link_memory",
                            "concept": "deposit-addresses",
                            "role": "warns_about",
                            "memory_id": "deposit-warning-memory",
                            "evidence": [{"kind": "manual", "note": "Warning."}],
                        }
                    ],
                }
            ),
            uow,
            id_generator=_SequenceIdGenerator(),
        )

    with uow_factory() as uow:
        show = show_concept(
            ConceptShowRequest.model_validate(
                {
                    "schema_version": "concept.v1",
                    "repo_id": "repo-a",
                    "concept": "deposit-addresses",
                    "include": ["memory_links"],
                }
            ),
            uow,
        )

    roles = {link["role"] for link in show.data["concept"]["memory_links"]}
    assert roles == {"warns_about"}


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
