"""This module defines pure create-policy planning helpers."""

from typing import Any

from app.core.contracts.planned_effects import (
    AssociationUpsertAndObserveEffectParams,
    CreatePlanIds,
    MemoryCreateEffectParams,
    MemoryEmbeddingUpsertEffectParams,
    MemoryEvidenceAttachEffectParams,
    PlannedEffect,
    ProblemAttemptCreateEffectParams,
    make_side_effect,
)
from app.core.entities.associations import AssociationSourceMode, AssociationState
from app.core.entities.memory import MemoryKind


def build_create_plan(
    payload: dict[str, Any],
    *,
    plan_ids: CreatePlanIds,
    embedding_model: str = "unknown",
) -> list[PlannedEffect]:
    """This function converts a validated create payload into deterministic side effects."""

    memory = payload["memory"]
    repo_id = payload["repo_id"]
    memory_id = plan_ids.memory_id
    plan: list[PlannedEffect] = [
        make_side_effect(
            "memory.create",
            MemoryCreateEffectParams(
                memory_id=memory_id,
                repo_id=repo_id,
                scope=memory["scope"],
                kind=memory["kind"],
                text=memory["text"],
            ),
        ),
        make_side_effect(
            "memory_embedding.upsert",
            MemoryEmbeddingUpsertEffectParams(
                memory_id=memory_id,
                model=embedding_model,
                text=memory["text"],
            ),
        ),
        make_side_effect(
            "memory_evidence.attach",
            MemoryEvidenceAttachEffectParams(
                memory_id=memory_id,
                repo_id=repo_id,
                refs=tuple(memory["evidence_refs"]),
            ),
        ),
    ]

    problem_id = (memory.get("links") or {}).get("problem_id")
    if memory["kind"] in {MemoryKind.SOLUTION.value, MemoryKind.FAILED_TACTIC.value} and problem_id:
        plan.append(
            make_side_effect(
                "problem_attempt.create",
                ProblemAttemptCreateEffectParams(
                    problem_id=problem_id,
                    attempt_id=memory_id,
                    role=memory["kind"],
                ),
            )
        )

    associations = (memory.get("links") or {}).get("associations", [])
    if len(plan_ids.association_edge_ids) < len(associations):
        raise ValueError("create plan ids missing association edge ids")
    if len(plan_ids.association_observation_ids) < len(associations):
        raise ValueError("create plan ids missing association observation ids")

    for index, association in enumerate(associations):
        confidence = association.get("confidence")
        salience = association.get("salience")
        plan.append(
            make_side_effect(
                "association.upsert_and_observe",
                AssociationUpsertAndObserveEffectParams(
                    repo_id=repo_id,
                    edge_id=plan_ids.association_edge_ids[index],
                    from_memory_id=memory_id,
                    to_memory_id=association["to_memory_id"],
                    relation_type=association["relation_type"],
                    source_mode=AssociationSourceMode.AGENT.value,
                    state=AssociationState.TENTATIVE.value,
                    strength=confidence if confidence is not None else 0.5,
                    observation_id=plan_ids.association_observation_ids[index],
                    observation_source="agent_explicit",
                    valence=confidence if confidence is not None else 0.5,
                    salience=salience if salience is not None else 0.5,
                    evidence_refs=tuple(memory["evidence_refs"]),
                ),
            )
        )
    return plan
