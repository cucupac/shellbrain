"""Request-shape contracts for update-path requests."""

from app.entrypoints.cli.request_parsing.payload_validation import validate_update_schema


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
            "type": "update_lifecycle",
            "status": "wrong",
            "rationale": "Contradicted by later evidence.",
            "actor": "manual",
            "evidence": [{"kind": "manual", "note": "Verified."}],
        },
    }

    request, errors = validate_update_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert "op" in fields
    assert "repo_id" in fields


def test_update_rejects_retired_archive_state_type() -> None:
    """archive_state should not remain a compatibility alias for lifecycle state."""

    payload = {
        "memory_id": "m-1",
        "update": {
            "type": "archive_state",
            "archived": True,
        },
    }

    request, errors = validate_update_schema(payload)

    assert request is None
    assert any(error.code.value == "schema_error" for error in errors)


def test_update_lifecycle_requires_rationale_actor_and_evidence() -> None:
    """lifecycle updates should not accept unaudited state changes."""

    payload = {
        "memory_id": "m-1",
        "update": {
            "type": "update_lifecycle",
            "status": "wrong",
        },
    }

    request, errors = validate_update_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert "update.update_lifecycle.rationale" in fields
    assert "update.update_lifecycle.actor" in fields
    assert "update.update_lifecycle.evidence" in fields


def test_update_lifecycle_accepts_manual_evidence() -> None:
    """manual evidence should be valid for auditable lifecycle updates."""

    payload = {
        "memory_id": "m-1",
        "update": {
            "type": "update_lifecycle",
            "status": "wrong",
            "rationale": "Contradicted by later evidence.",
            "actor": "manual",
            "evidence": [{"kind": "manual", "note": "Verified."}],
        },
    }

    request, errors = validate_update_schema(payload)

    assert errors == []
    assert request is not None


def test_update_accepts_batch_utility_vote_payloads() -> None:
    """update requests should always accept batch utility-vote payloads."""

    payload = {
        "updates": [
            {
                "memory_id": "m-1",
                "update": {
                    "type": "utility_vote",
                    "problem_id": "problem-1",
                    "vote": 1.0,
                },
            },
            {
                "memory_id": "m-2",
                "update": {
                    "type": "utility_vote",
                    "problem_id": "problem-1",
                    "vote": -1.0,
                },
            },
        ]
    }

    request, errors = validate_update_schema(payload)

    assert errors == []
    assert request is not None


def test_update_association_requires_explicit_strength_values() -> None:
    """association_link updates should not invent confidence or salience defaults."""

    payload = {
        "memory_id": "problem-1",
        "update": {
            "type": "association_link",
            "to_memory_id": "fact-1",
            "relation_type": "depends_on",
            "evidence_refs": ["session://1"],
        },
    }

    request, errors = validate_update_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert "update.association_link.confidence" in fields
    assert "update.association_link.salience" in fields
