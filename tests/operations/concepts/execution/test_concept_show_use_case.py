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
                        "evidence",
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
    assert payload["relations"][0]["subject"]["ref"] == "deposit-addresses"
    assert payload["relations"][0]["object"]["name"] == "Deposit Lifecycle"
    assert {item["target_type"] for item in payload["evidence"]} == {
        "claim",
        "relation",
    }
    assert all(item["note"] == "Seeded from planning." for item in payload["evidence"])
    assert all(item["created_at"] for item in payload["evidence"])
    assert payload["preview_concept"]["name"] == "Deposit Addresses"
    assert payload["preview_concept"]["claim_count"] == 1
    assert payload["status_rollup"]["active"] == 2

    with uow_factory() as uow:
        grounded = show_concept(
            ConceptShowRequest(
                schema_version="concept.v1",
                repo_id="repo-a",
                concept="deposit-lifecycle",
                include=["groundings", "evidence"],
            ),
            uow,
        ).data["concept"]
    grounding = grounded["groundings"][0]
    assert grounding["anchor"]["locator"] == {"path": "app/deposit_addresses.py"}
    assert grounding["anchor"]["created_at"]
    assert grounding["observed_at"]
    assert any(item["target_id"] == grounding["id"] for item in grounded["evidence"])
    assert "relations" not in grounded
    assert "memory_links" not in grounded


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

    link = show.data["concept"]["memory_links"][0]
    assert link["role"] == "warns_about"
    assert link["memory_id"] == "deposit-warning-memory"
    assert link["kind"] == "fact"
    assert link["text"] == "Deposit address cache misses can mislead retries."
    assert link["memory_status"] == "active"
    assert link["memory_created_at"]
    assert "evidence" not in show.data["concept"]


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


def test_bulk_bundles_preserve_typed_evidence_lifecycle_and_repo_scope(uow_factory):
    """Batching must not leak evidence when record tables reuse an ID."""
    from sqlalchemy import event, update
    from app.core.entities.concepts import (
        Concept,
        ConceptKind,
        ConceptLifecycleEvent,
        ConceptLifecycleTargetType,
        ConceptLifecycleStatus,
        ConceptCreatedBy,
    )
    from app.infrastructure.db.runtime.models.evidence import evidence_links

    _seed_deposit_addresses(uow_factory)
    with uow_factory() as uow:
        first = uow.concepts.get_concept_bundle(
            repo_id="repo-a", concept_ref="deposit-addresses"
        )
        first_id = first["concept"].id
        second_id = first["relations"][0].object_concept_id
        shared_id = first["relations"][0].id
        claim_id = first["claims"][0].id
        uow.concepts.add_concept(
            Concept(
                id="third",
                repo_id="repo-a",
                slug="third",
                name="Third",
                kind=ConceptKind.DOMAIN,
            ),
            [],
        )
        uow.concepts.add_concept(
            Concept(
                id="foreign",
                repo_id="repo-b",
                slug="foreign",
                name="Foreign",
                kind=ConceptKind.DOMAIN,
            ),
            [],
        )
        uow.concepts._session.execute(
            update(concept_claims)
            .where(concept_claims.c.id == claim_id)
            .values(id=shared_id, concept_id="third", status="archived")
        )
        uow.concepts._session.execute(
            update(evidence_links)
            .where(
                evidence_links.c.target_type == "concept_claim",
                evidence_links.c.target_id == claim_id,
            )
            .values(target_id=shared_id)
        )
        uow.concepts.add_lifecycle_event(
            ConceptLifecycleEvent(
                id="event",
                repo_id="repo-a",
                target_type=ConceptLifecycleTargetType.CLAIM,
                target_id=shared_id,
                from_status=ConceptLifecycleStatus.ACTIVE,
                to_status=ConceptLifecycleStatus.ARCHIVED,
                rationale="Old definition",
                actor=ConceptCreatedBy.MANUAL,
            )
        )
        statements = []
        connection = uow.concepts._session.connection()

        def count(*args):
            statements.append(args[2])

        event.listen(connection, "before_cursor_execute", count)
        try:
            assert (
                uow.concepts.get_concept_bundles(
                    include_evidence=True, repo_id="repo-a", concept_ids=[]
                )
                == {}
            )
            assert statements == []
            bundles = uow.concepts.get_concept_bundles(
                include_evidence=True,
                repo_id="repo-a",
                concept_ids=["third", second_id, "missing", "foreign", first_id],
                include_lifecycle_events=True,
            )
        finally:
            event.remove(connection, "before_cursor_execute", count)
        assert len(statements) == 9
        statements.clear()
        event.listen(connection, "before_cursor_execute", count)
        try:
            lean_bundles = uow.concepts.get_concept_bundles(
                repo_id="repo-a",
                concept_ids=list(bundles),
                include_evidence=False,
                include_lifecycle_events=True,
            )
        finally:
            event.remove(connection, "before_cursor_execute", count)
        assert len(statements) == 8
        assert lean_bundles == {
            key: {**bundle, "evidence": []} for key, bundle in bundles.items()
        }
        assert set(bundles) == {first_id, second_id, "third"}
        assert bundles[first_id]["relations"] == bundles[second_id]["relations"]
        assert bundles[first_id]["lifecycle_events"] == []
        assert bundles["third"]["lifecycle_events"][0].id == "event"
        assert bundles["third"]["claims"][0].lifecycle.status.value == "archived"
        assert {item.target_type.value for item in bundles["third"]["evidence"]} == {
            "claim"
        }
        assert {item.target_type.value for item in bundles[first_id]["evidence"]} == {
            "relation"
        }
        assert (
            bundles[second_id]["anchors"][0].id
            == bundles[second_id]["groundings"][0].anchor_id
        )
        for concept_id, bundle in bundles.items():
            assert bundle == uow.concepts.get_concept_bundle(
                repo_id="repo-a", concept_ref=concept_id, include_lifecycle_events=True
            )
        assert bundles == uow.concepts.get_concept_bundles(
            include_evidence=True,
            repo_id="repo-a",
            concept_ids=list(reversed(bundles)),
            include_lifecycle_events=True,
        )
