"""Effect-ordering contracts for create execution."""

from app.core.policies.memories.add_plan import build_create_plan
from app.core.use_cases.memories.add.result import CreatePlanIds
from app.core.use_cases.memories.effect_plan import EffectType


def test_create_plan_preserves_deterministic_effect_ordering_by_operation_type() -> (
    None
):
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
        EffectType.MEMORY_CREATE,
        EffectType.MEMORY_EMBEDDING_UPSERT,
        EffectType.MEMORY_EVIDENCE_ATTACH,
        EffectType.PROBLEM_ATTEMPT_CREATE,
        EffectType.ASSOCIATION_UPSERT_AND_OBSERVE,
    ]

    plan_ids = CreatePlanIds(
        memory_id="memory-1",
        association_edge_ids=("edge-1",),
        association_observation_ids=("observation-1",),
    )
    first_plan = build_create_plan(
        payload, plan_ids=plan_ids, embedding_model="stub-v1"
    )
    second_plan = build_create_plan(
        payload, plan_ids=plan_ids, embedding_model="stub-v1"
    )

    assert [effect.effect_type for effect in first_plan] == expected_effect_types
    assert [effect.effect_type for effect in second_plan] == expected_effect_types
