"""Request-shape contracts for the concept endpoint."""

from app.periphery.cli.schema_validation import validate_concept_schema


def test_concept_apply_should_accept_typed_batch_actions_with_inline_evidence() -> None:
    """concept apply should accept the phase-one typed action protocol."""

    request, errors = validate_concept_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "mode": "apply",
            "actions": [
                {
                    "type": "upsert_concept",
                    "slug": "deposit-addresses",
                    "name": "Deposit Addresses",
                    "kind": "domain",
                    "aliases": ["deposit address"],
                },
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
    assert request.mode == "apply"


def test_concept_apply_should_reject_truth_bearing_actions_without_evidence() -> None:
    """truth-bearing concept actions should always require inline evidence."""

    request, errors = validate_concept_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "mode": "apply",
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


def test_concept_show_should_require_a_concept_reference() -> None:
    """concept show should always require the target concept."""

    request, errors = validate_concept_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "mode": "show",
            "include": ["preview_concept"],
        }
    )

    assert request is None
    assert errors


def test_concept_contract_should_reject_unknown_fields() -> None:
    """concept endpoint contracts should stay strict."""

    request, errors = validate_concept_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "mode": "apply",
            "actions": [{"type": "upsert_concept", "slug": "x", "name": "X", "kind": "domain", "extra": True}],
        }
    )

    assert request is None
    assert errors
