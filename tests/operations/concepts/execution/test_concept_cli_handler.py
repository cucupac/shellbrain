"""CLI-handler contracts for the JSON-first concept endpoints."""

from collections.abc import Callable
from pathlib import Path

from app.core.use_cases.concepts.add.request import ConceptAddRequest
from app.core.use_cases.concepts.update.request import ConceptUpdateRequest
from tests.operations._shared.handler_calls import handle_concept_add, handle_concept_update
from app.infrastructure.db.runtime.models.concepts import concepts
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork


def test_concept_add_handler_should_add_json_payload(
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
    tmp_path: Path,
) -> None:
    """concept add handler should expose one JSON-first add surface."""

    result = handle_concept_add(
        ConceptAddRequest.model_validate(
            {
                "schema_version": "concept.v1",
                "actions": [
                    {
                        "type": "add_concept",
                        "slug": "deposit-addresses",
                        "name": "Deposit Addresses",
                        "kind": "domain",
                    }
                ],
                "repo_id": "repo-a",
            }
        ),
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
        repo_root=tmp_path,
    )

    assert result["status"] == "ok"
    rows = fetch_rows(concepts, concepts.c.slug == "deposit-addresses")
    assert len(rows) == 1


def test_concept_update_handler_should_use_distinct_update_path(
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
    tmp_path: Path,
) -> None:
    """concept update handler should mutate an existing concept without delegating to add."""

    handle_concept_add(
        ConceptAddRequest.model_validate(
            {
                "schema_version": "concept.v1",
                "actions": [
                    {
                        "type": "add_concept",
                        "slug": "deposit-addresses",
                        "name": "Deposit Addresses",
                        "kind": "domain",
                    }
                ],
                "repo_id": "repo-a",
            }
        ),
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
        repo_root=tmp_path,
    )

    result = handle_concept_update(
        ConceptUpdateRequest.model_validate(
            {
                "schema_version": "concept.v1",
                "actions": [
                    {
                        "type": "update_concept",
                        "concept": "deposit-addresses",
                        "name": "Deposit Address Graph",
                    }
                ],
                "repo_id": "repo-a",
            }
        ),
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
        repo_root=tmp_path,
    )

    assert result["status"] == "ok"
    rows = fetch_rows(concepts, concepts.c.slug == "deposit-addresses")
    assert rows[0]["name"] == "Deposit Address Graph"


def test_concept_update_handler_should_fail_when_concept_is_missing(
    uow_factory: Callable[[], PostgresUnitOfWork],
    tmp_path: Path,
) -> None:
    """concept update handler should not create missing concept containers."""

    result = handle_concept_update(
        ConceptUpdateRequest.model_validate(
            {
                "schema_version": "concept.v1",
                "actions": [
                    {
                        "type": "update_concept",
                        "concept": "deposit-addresses",
                        "name": "Deposit Address Graph",
                    }
                ],
                "repo_id": "repo-a",
            }
        ),
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
        repo_root=tmp_path,
    )

    assert result["status"] == "error"
    assert result["errors"][0]["code"] == "not_found"
    assert "Concept not found" in result["errors"][0]["message"]
