"""Request-shape contracts for the concept endpoints."""

from app.entrypoints.cli.request_parsing.payload_validation import (
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


def test_concept_update_should_still_accept_memory_evidence() -> None:
    """memory remains a valid evidence kind even though it is not an anchor kind."""

    request, errors = validate_concept_update_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "add_claim",
                    "concept": "deposit-addresses",
                    "claim_type": "definition",
                    "text": "Evidence can point at a Shellbrain memory.",
                    "evidence": [{"kind": "memory", "memory_id": "mem-1"}],
                },
            ],
        }
    )

    assert errors == []
    assert request is not None
    evidence = request.actions[0].evidence[0]
    assert evidence.kind == "memory"
    assert evidence.memory_id == "mem-1"


def test_concept_update_should_accept_lifecycle_updates_with_evidence() -> None:
    """concept update should accept auditable lifecycle mutations."""

    request, errors = validate_concept_update_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "update_lifecycle",
                    "target_type": "claim",
                    "target_id": "claim-1",
                    "status": "wrong",
                    "rationale": "Contradicted by later implementation evidence.",
                    "actor": "manual",
                    "confidence": 0.1,
                    "evidence": [{"kind": "manual", "note": "Verified in review."}],
                },
            ],
        }
    )

    assert errors == []
    assert request is not None
    action = request.actions[0]
    assert action.type == "update_lifecycle"
    assert action.status == "wrong"


def test_concept_update_should_reject_lifecycle_updates_without_evidence_or_rationale() -> None:
    """lifecycle mutations should require evidence and a rationale."""

    request, errors = validate_concept_update_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "update_lifecycle",
                    "target_type": "claim",
                    "target_id": "claim-1",
                    "status": "wrong",
                    "rationale": " ",
                    "actor": "manual",
                    "evidence": [],
                },
            ],
        }
    )

    assert request is None
    assert errors


def test_concept_update_should_require_superseding_target_for_superseded_lifecycle() -> None:
    """superseded lifecycle updates should name a replacement record."""

    request, errors = validate_concept_update_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "update_lifecycle",
                    "target_type": "claim",
                    "target_id": "claim-1",
                    "status": "superseded",
                    "rationale": "Replaced by newer claim.",
                    "actor": "manual",
                    "evidence": [{"kind": "manual", "note": "Replacement noted."}],
                },
            ],
        }
    )

    assert request is None
    assert errors


def test_concept_update_should_reject_superseding_target_for_non_superseded_lifecycle() -> None:
    """non-superseded lifecycle updates should not accept replacement pointers."""

    request, errors = validate_concept_update_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "repo-a",
            "actions": [
                {
                    "type": "update_lifecycle",
                    "target_type": "claim",
                    "target_id": "claim-1",
                    "status": "active",
                    "superseded_by_id": "claim-2",
                    "rationale": "Revalidate the claim.",
                    "actor": "manual",
                    "evidence": [{"kind": "manual", "note": "Replacement invalid."}],
                },
            ],
        }
    )

    assert request is None
    assert errors


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


def test_concept_add_should_reject_blank_required_strings() -> None:
    """concept add should not accept whitespace-only identifiers or labels."""

    request, errors = validate_concept_add_schema(
        {
            "schema_version": "concept.v1",
            "repo_id": "   ",
            "actions": [
                {
                    "type": "add_concept",
                    "slug": "   ",
                    "name": "   ",
                    "kind": "domain",
                    "aliases": ["   "],
                }
            ],
        }
    )

    assert request is None
    fields = {error.field for error in errors}
    assert "repo_id" in fields
    assert "actions.0.slug" in fields
    assert "actions.0.name" in fields
    assert "actions.0.aliases" in fields
