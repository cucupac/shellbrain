"""Schema contracts for write-path requests."""

from app.core.validation.schema_validation import validate_create_schema, validate_update_schema


def test_create_rejects_unknown_fields() -> None:
    """create requests should always reject unknown fields."""

    payload = {
        "op": "create",
        "repo_id": "repo-a",
        "memory": {
            "text": "Unknown fields should fail.",
            "scope": "repo",
            "kind": "problem",
            "confidence": 0.5,
            "evidence_refs": ["session://1"],
            "unknown": "nope",
        },
    }

    request, errors = validate_create_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)


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


def test_schema_enforces_bounds_and_unique_evidence() -> None:
    """create requests should always enforce confidence bounds and unique evidence refs."""

    payload = {
        "op": "create",
        "repo_id": "repo-a",
        "memory": {
            "text": "Bounds and uniqueness should fail.",
            "scope": "repo",
            "kind": "problem",
            "confidence": 1.5,
            "evidence_refs": ["session://1", "session://1"],
        },
    }

    request, errors = validate_create_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert "memory.confidence" in fields
    assert "memory.evidence_refs" in fields


def test_schema_requires_non_empty_evidence_refs() -> None:
    """create requests should always require at least one evidence ref."""

    payload = {
        "op": "create",
        "repo_id": "repo-a",
        "memory": {
            "text": "Evidence refs should be required.",
            "scope": "repo",
            "kind": "problem",
            "confidence": 0.8,
            "evidence_refs": [],
        },
    }

    request, errors = validate_create_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)
    assert any(error.field == "memory.evidence_refs" for error in errors)
