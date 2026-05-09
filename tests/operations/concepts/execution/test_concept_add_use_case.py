"""Execution contracts for the concept-add use case."""

from collections.abc import Callable

from app.core.contracts.concepts import ConceptAddRequest
from app.core.ports.runtime.idgen import IIdGenerator
from app.core.use_cases.concepts.add import add_concepts
from app.infrastructure.db.runtime.models.concepts import concepts
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork


class _SequenceIdGenerator(IIdGenerator):
    def __init__(self) -> None:
        self._next = 0

    def new_id(self) -> str:
        self._next += 1
        return f"concept-id-{self._next}"


def test_concept_add_should_create_new_concept_containers(
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """concept add should create only missing concept containers."""

    with uow_factory() as uow:
        result = add_concepts(
            _deposit_concepts_request(), uow, id_generator=_SequenceIdGenerator()
        )
    assert result.data["added_count"] == 4
    assert len(fetch_rows(concepts)) == 4


def test_concept_add_should_fail_if_concept_exists(
    uow_factory: Callable[[], PostgresUnitOfWork],
) -> None:
    """concept add should not upsert an existing concept."""

    with uow_factory() as uow:
        add_concepts(
            _deposit_concepts_request(), uow, id_generator=_SequenceIdGenerator()
        )

    with uow_factory() as uow:
        try:
            add_concepts(
                _deposit_concepts_request(), uow, id_generator=_SequenceIdGenerator()
            )
        except ValueError as exc:
            assert "Concept already exists: deposit-addresses" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("Expected duplicate concept add to fail")


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
