"""Schema contracts for read-path requests."""

from app.core.validation.schema_validation import validate_read_schema


def test_read_rejects_unknown_fields() -> None:
    """read requests should always reject unknown fields."""

    payload = {
        "op": "read",
        "repo_id": "repo-a",
        "mode": "targeted",
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
        "repo_id": "repo-a",
        "mode": "targeted",
        "query": "find deployment issue memory",
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)


def test_read_requires_non_empty_query() -> None:
    """read requests should always require non-empty query text."""

    payload = {
        "op": "read",
        "repo_id": "repo-a",
        "mode": "targeted",
        "query": "",
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)
    assert any(error.field == "query" for error in errors)


def test_read_kinds_reject_non_ratified_values() -> None:
    """read requests should always limit kinds filters to ratified memory kinds."""

    payload = {
        "op": "read",
        "repo_id": "repo-a",
        "mode": "targeted",
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
        "repo_id": "repo-a",
        "mode": "targeted",
        "query": "find deployment issue memory",
        "kinds": ["problem", "problem"],
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)
    assert any((error.field or "").startswith("kinds") for error in errors)


def test_read_enforces_limit_and_expand_bounds() -> None:
    """read requests should always enforce limit and expansion knob bounds."""

    payload = {
        "op": "read",
        "repo_id": "repo-a",
        "mode": "targeted",
        "query": "find deployment issue memory",
        "limit": 0,
        "expand": {
            "semantic_hops": 4,
            "max_association_depth": 0,
            "min_association_strength": 1.1,
        },
    }

    request, errors = validate_read_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert "limit" in fields
    assert "expand.semantic_hops" in fields
    assert "expand.max_association_depth" in fields
    assert "expand.min_association_strength" in fields
