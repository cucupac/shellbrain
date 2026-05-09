"""Request-shape contracts for the concept endpoints."""

from app.entrypoints.cli.protocol.payload_validation import (
    validate_concept_add_schema,
    validate_concept_show_schema,
    validate_concept_update_schema,
)


def test_concept_add_should_accept_typed_concept_actions() -> None:
    """concept add should accept concept-container creation only."""

    request, errors = validate_concept_add_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "add_concept",
                    "slug": "deposit-addresses",
                    "name": "Deposit Addresses",
                    "kind": "domain",
                    "aliases": ["deposit address"],
                },
            ],
        }
    )

    assert errors == []
    assert request is not None
    assert request.actions[0].type == "add_concept"


def test_concept_update_should_accept_typed_batch_actions_with_inline_evidence() -> (
    None
):
    """concept update should accept truth-bearing graph actions."""

    request, errors = validate_concept_update_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "add_claim",
                    "concept": "deposit-addresses",
                    "claim_type": "definition",
                    "text": "Relay-controlled EOAs users send funds to.",
                    "evidence": [{"kind": "manual", "note": "Seeded from planning."}],
                },
            ],
        }
    )

    assert errors == []
    assert request is not None
    assert request.actions[0].type == "add_claim"


def test_concept_update_should_reject_truth_bearing_actions_without_evidence() -> None:
    """truth-bearing concept update actions should always require inline evidence."""

    request, errors = validate_concept_update_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "add_claim",
                    "concept": "deposit-addresses",
                    "claim_type": "definition",
                    "text": "Missing evidence.",
                }
            ],
        }
    )

    assert request is None
    assert errors
    assert errors[0].code.value == "schema_error"


def test_concept_update_action_should_require_a_mutable_field() -> None:
    """update_concept should not accept no-op concept updates."""

    request, errors = validate_concept_update_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [{"type": "update_concept", "concept": "deposit-addresses"}],
        }
    )

    assert request is None
    assert errors


def test_concept_show_should_require_a_concept_reference() -> None:
    """concept show should always require the target concept."""

    request, errors = validate_concept_show_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "include": ["preview_concept"],
        }
    )

    assert request is None
    assert errors


def test_concept_contract_should_reject_unknown_fields() -> None:
    """concept endpoint contracts should stay strict."""

    request, errors = validate_concept_add_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "add_concept",
                    "slug": "x",
                    "name": "X",
                    "kind": "domain",
                    "extra": True,
                }
            ],
        }
    )

    assert request is None
    assert errors
