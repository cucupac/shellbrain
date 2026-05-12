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
            "type": "archive_state",
            "archived": True,
        },
    }

    request, errors = validate_update_schema(payload)

    assert request is None
    fields = {error.field for error in errors}
    assert "op" in fields
    assert "repo_id" in fields


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


def test_update_accepts_matures_into_association_links() -> None:
    """update requests should always accept matures_into association links."""

    payload = {
        "memory_id": "frontier-1",
        "update": {
            "type": "association_link",
            "to_memory_id": "fact-1",
            "relation_type": "matures_into",
            "evidence_refs": ["session://1"],
        },
    }

    request, errors = validate_update_schema(payload)

    assert errors == []
    assert request is not None
