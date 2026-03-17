"""Effect-ordering contracts for create execution."""

from shellbrain.core.policies.create_policy.pipeline import build_create_plan


def test_create_plan_preserves_deterministic_effect_ordering_by_operation_type() -> None:
    """create plans should always preserve deterministic effect ordering by operation type."""

    payload = {
        "op": "create",
        "repo_id": "repo-a",
        "memory_id": "memory-1",
        "memory": {
            "text": "A solution with one explicit association.",
            "scope": "repo",
            "kind": "solution",
            "links": {
                "problem_id": "problem-1",
                "associations": [
                    {
                        "to_memory_id": "target-1",
                        "relation_type": "depends_on",
                        "confidence": 0.7,
                    }
                ],
            },
            "evidence_refs": ["session://1"],
        },
    }

    expected_effect_types = [
        "memory.create",
        "memory_embedding.upsert",
        "memory_evidence.attach",
        "problem_attempt.create",
        "association.upsert_and_observe",
    ]

    first_plan = build_create_plan(payload, embedding_model="stub-v1")
    second_plan = build_create_plan(payload, embedding_model="stub-v1")

    assert [effect["effect_type"] for effect in first_plan] == expected_effect_types
    assert [effect["effect_type"] for effect in second_plan] == expected_effect_types
