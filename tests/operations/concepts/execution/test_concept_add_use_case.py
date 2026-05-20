"""Execution contracts for the concept-add use case."""

from collections.abc import Callable

from app.core.use_cases.concepts.add.request import ConceptAddRequest
from app.core.ports.embeddings.provider import IEmbeddingProvider
from app.core.ports.system.idgen import IIdGenerator
from app.core.use_cases.concepts.add import add_concepts
from app.infrastructure.db.runtime.models.concepts import concept_embeddings, concepts
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


def test_concept_add_should_persist_embeddings_for_new_concepts(
    uow_factory: Callable[[], PostgresUnitOfWork],
    stub_embedding_provider: IEmbeddingProvider,
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """concept add should maintain concept_embeddings when embedding support is wired."""

    with uow_factory() as uow:
        result = add_concepts(
            _deposit_concepts_request(),
            uow,
            id_generator=_SequenceIdGenerator(),
            embedding_provider=stub_embedding_provider,
            embedding_model="stub-v1",
        )

    assert result.data["added_count"] == 4
    rows = fetch_rows(concept_embeddings)
    assert len(rows) == 4
    assert {row["model"] for row in rows} == {"stub-v1"}
    assert {row["dim"] for row in rows} == {4}
    assert all(row["source_hash"] for row in rows)


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
