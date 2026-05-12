"""Link-rule contracts for create-path requests."""

from app.core.use_cases.memories.add.request import MemoryAddRequest
from app.core.policies.memories.link_rules import validate_create_semantics


def test_solution_requires_problem_id() -> None:
    """solution memories should always include links.problem_id."""

    request = MemoryAddRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Try larger timeout.",
                "scope": "repo",
                "kind": "solution",
                "evidence_refs": ["session://1"],
            },
        }
    )

    errors = validate_create_semantics(request)

    assert any(error.code.value == "semantic_error" for error in errors)
    assert any(error.field == "memory.links.problem_id" for error in errors)


def test_failed_tactic_requires_problem_id() -> None:
    """failed_tactic memories should always include links.problem_id."""

    request = MemoryAddRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Restarting the service did not help.",
                "scope": "repo",
                "kind": "failed_tactic",
                "evidence_refs": ["session://1"],
            },
        }
    )

    errors = validate_create_semantics(request)

    assert any(error.code.value == "semantic_error" for error in errors)
    assert any(error.field == "memory.links.problem_id" for error in errors)


def test_non_attempt_kinds_forbid_problem_id() -> None:
    """non-attempt kinds should always reject links.problem_id."""

    for kind in ["problem", "fact", "preference", "change", "frontier"]:
        request = MemoryAddRequest.model_validate(
            {
                "op": "create",
                "repo_id": "repo-a",
                "memory": {
                    "text": f"{kind} payload.",
                    "scope": "repo",
                    "kind": kind,
                    "links": {"problem_id": "problem-1"},
                    "evidence_refs": ["session://1"],
                },
            }
        )

        errors = validate_create_semantics(request)

        assert any(error.code.value == "semantic_error" for error in errors)
        assert any(error.field == "memory.links.problem_id" for error in errors)


def test_create_rejects_duplicate_association_pairs() -> None:
    """create association lists should always reject duplicate target+relation pairs."""

    request = MemoryAddRequest.model_validate(
        {
            "op": "create",
            "repo_id": "repo-a",
            "memory": {
                "text": "Duplicate association pair.",
                "scope": "repo",
                "kind": "problem",
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
