"""Request-shape contracts for create-path requests."""

from app.periphery.cli.hydration import hydrate_create_payload
from app.periphery.cli.schema_validation import validate_create_schema


def test_create_rejects_unknown_fields() -> None:
    """create requests should always reject unknown fields."""

    payload = {
        "memory": {
            "text": "Unknown fields should fail.",
            "scope": "repo",
            "kind": "problem",
            "evidence_refs": ["session://1"],
            "unknown": "nope",
        },
    }

    request, errors = validate_create_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)


def test_create_enforces_unique_evidence() -> None:
    """create requests should always enforce unique evidence refs."""

    payload = {
        "memory": {
            "text": "Bounds and uniqueness should fail.",
            "scope": "repo",
            "kind": "problem",
            "evidence_refs": ["session://1", "session://1"],
        },
    }

    request, errors = validate_create_schema(payload)

    assert request is None
    assert any(error.field == "memory.evidence_refs" for error in errors)


def test_create_requires_non_empty_evidence_refs() -> None:
    """create requests should always require at least one evidence ref."""

    payload = {
        "memory": {
            "text": "Evidence refs should be required.",
            "scope": "repo",
            "kind": "problem",
            "evidence_refs": [],
        },
    }

    request, errors = validate_create_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)
    assert any(error.field == "memory.evidence_refs" for error in errors)


def test_create_rejects_transport_fields_at_agent_interface() -> None:
    """create requests should always reject op/repo_id at the agent interface."""

    payload = {
        "op": "create",
        "repo_id": "repo-a",
        "memory": {
            "text": "Agent create payload.",
            "kind": "problem",
            "evidence_refs": ["session://1"],
        },
    }

    request, errors = validate_create_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert "op" in fields
    assert "repo_id" in fields


def test_create_hydration_infers_configured_scope_default() -> None:
    """create hydration should always infer configured scope when omitted."""

    hydrated = hydrate_create_payload(
        {
            "memory": {
                "text": "Repo-scoped defaulted memory.",
                "kind": "problem",
                "evidence_refs": ["session://1"],
            }
        },
        inferred_repo_id="repo-inferred",
        defaults={"scope": "global"},
    )

    assert hydrated == {
        "op": "create",
        "repo_id": "repo-inferred",
        "memory": {
            "text": "Repo-scoped defaulted memory.",
            "scope": "global",
            "kind": "problem",
            "evidence_refs": ["session://1"],
        },
    }


def test_create_hydration_preserves_explicit_scope() -> None:
    """create hydration should always preserve explicit scope over configured defaults."""

    payload = {
        "op": "create",
        "repo_id": "repo-explicit",
        "memory": {
            "text": "Explicit create payload.",
            "scope": "repo",
            "kind": "problem",
            "evidence_refs": ["session://1"],
        },
    }

    hydrated = hydrate_create_payload(
        payload,
        inferred_repo_id="repo-inferred",
        defaults={"scope": "global"},
    )

    assert hydrated == payload
