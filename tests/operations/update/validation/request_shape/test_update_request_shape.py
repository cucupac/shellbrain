"""Request-shape contracts for update-path requests."""

from app.periphery.cli.schema_validation import validate_update_schema


def test_update_rejects_unknown_update_type() -> None:
    """update requests should always reject unrecognized update.type values."""

    payload = {
        "op": "update",
        "repo_id": "repo-a",
        "memory_id": "m-1",
        "mode": "commit",
        "update": {
            "type": "unknown_update",
        },
    }

    request, errors = validate_update_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)


def test_update_rejects_invalid_operation() -> None:
    """update requests should always reject op values other than update."""

    payload = {
        "op": "create",
        "repo_id": "repo-a",
        "memory_id": "m-1",
        "mode": "commit",
        "update": {
            "type": "archive_state",
            "archived": True,
        },
    }

    request, errors = validate_update_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)
