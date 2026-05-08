"""CLI-handler contracts for the JSON-first concept endpoint."""

from collections.abc import Callable
from pathlib import Path

from app.startup.operations import handle_concept
from app.periphery.db.models.concepts import concepts
from app.periphery.db.uow import PostgresUnitOfWork


def test_concept_handler_should_apply_json_payload(
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
    tmp_path: Path,
) -> None:
    """concept handler should expose one JSON-first apply surface."""

    result = handle_concept(
        {
            "schema_version": "concept.v1",
            "mode": "apply",
            "actions": [
                {
                    "type": "upsert_concept",
                    "slug": "deposit-addresses",
                    "name": "Deposit Addresses",
                    "kind": "domain",
                }
            ],
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
        repo_root=tmp_path,
    )

    assert result["status"] == "ok"
    rows = fetch_rows(concepts, concepts.c.slug == "deposit-addresses")
    assert len(rows) == 1


def test_concept_handler_should_show_dynamic_preview_concept(
    uow_factory: Callable[[], PostgresUnitOfWork],
    tmp_path: Path,
) -> None:
    """concept handler show mode should return a dynamic preview_concept."""

    handle_concept(
        {
            "schema_version": "concept.v1",
            "mode": "apply",
            "actions": [
                {"type": "upsert_concept", "slug": "deposit-addresses", "name": "Deposit Addresses", "kind": "domain"}
            ],
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
        repo_root=tmp_path,
    )

    result = handle_concept(
        {
            "schema_version": "concept.v1",
            "mode": "show",
            "concept": "deposit-addresses",
            "include": ["preview_concept"],
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
        repo_root=tmp_path,
    )

    assert result["status"] == "ok"
    assert result["data"]["concept"]["preview_concept"]["name"] == "Deposit Addresses"
