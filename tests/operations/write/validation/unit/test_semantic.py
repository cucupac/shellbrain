"""Semantic contracts for write-path requests."""

from app.core.contracts.requests import MemoryCreateRequest, MemoryUpdateRequest
from app.core.validation.semantic_validation import validate_create_semantics, validate_update_semantics


def test_solution_requires_problem_id() -> None:
    """solution should always require links.problem_id."""

    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Try larger timeout.",
                "scope": "repo",
                "kind": "solution",
                "confidence": 0.8,
                "evidence_refs": ["session://1"],
            },
        }
    )

    errors = validate_create_semantics(request)

    assert any(error.code.value == "semantic_error" for error in errors)
    assert any(error.field == "memory.links.problem_id" for error in errors)


def test_failed_tactic_requires_problem_id() -> None:
    """failed_tactic should always require links.problem_id."""

    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Restarting the service did not help.",
                "scope": "repo",
                "kind": "failed_tactic",
                "confidence": 0.7,
                "evidence_refs": ["session://1"],
            },
        }
    )

    errors = validate_create_semantics(request)

    assert any(error.code.value == "semantic_error" for error in errors)
    assert any(error.field == "memory.links.problem_id" for error in errors)


def test_non_attempt_kinds_forbid_problem_id() -> None:
    """problem, fact, preference, and change should always forbid links.problem_id."""

    for kind in ["problem", "fact", "preference", "change"]:
        request = MemoryCreateRequest.model_validate(
            {
                "op": "create",
                "repo_id": "repo-a",
                "memory": {
                    "text": f"{kind} payload.",
                    "scope": "repo",
                    "kind": kind,
                    "confidence": 0.6,
                    "links": {"problem_id": "problem-1"},
                    "evidence_refs": ["session://1"],
                },
            }
        )

        errors = validate_create_semantics(request)

        assert any(error.code.value == "semantic_error" for error in errors)
        assert any(error.field == "memory.links.problem_id" for error in errors)


def test_create_rejects_duplicate_association_pairs() -> None:
    """create associations should always reject duplicate (to_memory_id, relation_type) pairs."""

    request = MemoryCreateRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Duplicate association pair.",
                "scope": "repo",
                "kind": "problem",
                "confidence": 0.5,
                "links": {
                    "associations": [
                        {"to_memory_id": "m-2", "relation_type": "depends_on"},
                        {"to_memory_id": "m-2", "relation_type": "depends_on"},
                    ]
                },
                "evidence_refs": ["session://1"],
            },
        }
    )

    errors = validate_create_semantics(request)

    assert any(error.code.value == "semantic_error" for error in errors)


def test_update_association_rejects_self_link() -> None:
    """association update should always reject self-links."""

    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "m-1",
            "mode": "commit",
            "update": {
                "type": "association_link",
                "to_memory_id": "m-1",
                "relation_type": "depends_on",
                "evidence_refs": ["session://1"],
            },
        }
    )

    errors = validate_update_semantics(request)

    assert any(error.code.value == "semantic_error" for error in errors)
    assert any(error.field == "update.to_memory_id" for error in errors)


def test_fact_update_requires_distinct_old_and_new() -> None:
    """fact_update_link should always require different old_fact_id and new_fact_id."""

    request = MemoryUpdateRequest.model_validate(
        {
            "op": "update",
            "repo_id": "repo-a",
            "memory_id": "change-1",
            "mode": "commit",
            "update": {
                "type": "fact_update_link",
                "old_fact_id": "fact-1",
                "new_fact_id": "fact-1",
            },
        }
    )

    errors = validate_update_semantics(request)

    assert any(error.code.value == "semantic_error" for error in errors)
    assert any(error.field == "update.new_fact_id" for error in errors)
