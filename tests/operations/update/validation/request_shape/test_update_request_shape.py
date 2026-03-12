"""Request-shape contracts for update-path requests."""

from app.periphery.cli.schema_validation import validate_update_schema


def test_update_rejects_unknown_update_type() -> None:
    """update requests should always reject unrecognized update.type values."""

    payload = {
        "memory_id": "m-1",
        "update": {
            "type": "unknown_update",
        },
    }

    request, errors = validate_update_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)


def test_update_rejects_transport_fields_at_agent_interface() -> None:
    """update requests should always reject op/repo_id at the agent interface."""

    payload = {
        "op": "update",
        "repo_id": "repo-a",
        "memory_id": "m-1",
        "update": {
            "type": "archive_state",
            "archived": True,
        },
    }

    request, errors = validate_update_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert "op" in fields
    assert "repo_id" in fields
