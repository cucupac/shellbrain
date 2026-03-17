"""Schema contracts for read-path requests."""

from shellbrain.periphery.cli.schema_validation import validate_read_schema


def test_read_rejects_unknown_fields() -> None:
    """read requests should always reject unknown fields."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "unknown": "nope",
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)


def test_read_rejects_invalid_operation() -> None:
    """read requests should always reject op values other than read."""

    payload = {
        "op": "create",
        "query": "find deployment issue memory",
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)


def test_read_requires_non_empty_query() -> None:
    """read requests should always require non-empty query text."""

    payload = {
        "op": "read",
        "query": "",
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)
    assert any(error.field == "query" for error in errors)


def test_read_kinds_reject_non_ratified_values() -> None:
    """read requests should always limit kinds filters to ratified shellbrain kinds."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "kinds": ["problem", "unknown_kind"],
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)
    assert any((error.field or "").startswith("kinds") for error in errors)


def test_read_kinds_reject_duplicates() -> None:
    """read requests should always require unique kinds filters."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "kinds": ["problem", "problem"],
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)
    assert any((error.field or "").startswith("kinds") for error in errors)


def test_read_rejects_config_override_knobs_at_agent_interface() -> None:
    """read requests should always reject config override knobs at the agent interface."""

    payload = {
        "op": "read",
        "query": "find deployment issue memory",
        "mode": "ambient",
        "include_global": False,
        "limit": 99,
        "expand": {
            "semantic_hops": 0,
        },
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert "mode" in fields
    assert "include_global" in fields
    assert "limit" in fields
    assert "expand" in fields
