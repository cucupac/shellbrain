"""Request-shape contracts for create-path requests."""

import pytest

from app.entrypoints.cli.request_parsing.hydration import hydrate_memory_add_payload
from app.entrypoints.cli.request_parsing.payload_validation import validate_create_schema


@pytest.fixture(autouse=True)
def clear_database() -> None:
    """Schema-only request-shape tests do not need integration database cleanup."""


@pytest.fixture(autouse=True)
def _seed_repo_a_evidence_events() -> None:
    """Schema-only request-shape tests do not need create integration fixtures."""


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


def test_create_rejects_blank_memory_text() -> None:
    """create requests should always require real memory text."""

    payload = {
        "memory": {
            "text": "   ",
            "scope": "repo",
            "kind": "problem",
            "evidence_refs": ["session://1"],
        },
    }

    request, errors = validate_create_schema(payload)

    assert request is None
    assert any(error.field == "memory.text" for error in errors)


def test_create_rejects_blank_evidence_ref_values() -> None:
    """create evidence refs should be concrete event references."""

    payload = {
        "memory": {
            "text": "Evidence refs should be real references.",
            "scope": "repo",
            "kind": "problem",
            "evidence_refs": ["   "],
        },
    }

    request, errors = validate_create_schema(payload)

    assert request is None
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

    hydrated = hydrate_memory_add_payload(
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

    hydrated = hydrate_memory_add_payload(
        payload,
        inferred_repo_id="repo-inferred",
        defaults={"scope": "global"},
    )

    assert hydrated == payload


def test_create_associations_require_explicit_strength_values() -> None:
    """create association links should not invent confidence or salience defaults."""

    payload = {
        "memory": {
            "text": "Open question about retrieval behavior.",
            "scope": "repo",
            "kind": "problem",
            "links": {
                "associations": [
                    {
                        "to_memory_id": "fact-1",
                        "relation_type": "depends_on",
                    }
                ]
            },
            "evidence_refs": ["session://1"],
        },
    }

    request, errors = validate_create_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert "memory.links.associations.0.confidence" in fields
    assert "memory.links.associations.0.salience" in fields


def test_create_rejects_related_memory_ids_until_supported() -> None:
    """related_memory_ids should not be accepted while create drops them."""

    payload = {
        "memory": {
            "text": "Open question about retrieval behavior.",
            "scope": "repo",
            "kind": "problem",
            "links": {"related_memory_ids": ["mem-related"]},
            "evidence_refs": ["session://1"],
        },
    }

    request, errors = validate_create_schema(payload)

    assert request is None
    assert any(error.field == "memory.links.related_memory_ids" for error in errors)
