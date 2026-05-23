"""This module defines pure create-policy planning helpers."""

from typing import Any

from app.core.use_cases.memories.add.result import CreatePlanIds
from app.core.use_cases.memories.effect_plan import (
    AssociationUpsertAndObserveEffectParams,
    MemoryAddEffectParams,
    MemoryEmbeddingUpsertEffectParams,
    EvidenceAttachEffectParams,
    PlannedEffect,
    StructuralProblemLinkEffectParams,
    make_side_effect,
)
from app.core.entities.associations import AssociationSourceMode, AssociationState
from app.core.entities.memories import (
    ConfidenceValue,
    EvidenceRefs,
    MemoryKind,
    SalienceValue,
)


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
    evidence_refs = EvidenceRefs.required(memory["evidence_refs"]).values
    plan: list[PlannedEffect] = [
        make_side_effect(
            "memory.create",
            MemoryAddEffectParams(
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
            "evidence.attach",
            EvidenceAttachEffectParams(
                memory_id=memory_id,
                repo_id=repo_id,
                refs=evidence_refs,
            ),
        ),
    ]

    problem_id = (memory.get("links") or {}).get("problem_id")
    if MemoryKind(memory["kind"]).requires_problem_link and problem_id:
        relation_id = _required_structural_relation_id(plan_ids, 0)
        plan.append(
            make_side_effect(
                "structural_problem_link.create",
                StructuralProblemLinkEffectParams(
                    relation_id=relation_id,
                    repo_id=repo_id,
                    problem_id=problem_id,
                    attempt_id=memory_id,
                    attempt_kind=memory["kind"],
                    evidence_refs=evidence_refs,
                ),
            )
        )

    associations = (memory.get("links") or {}).get("associations", [])
    if len(plan_ids.association_edge_ids) < len(associations):
        raise ValueError("create plan ids missing association edge ids")
    if len(plan_ids.association_observation_ids) < len(associations):
        raise ValueError("create plan ids missing association observation ids")

    for index, association in enumerate(associations):
        confidence = ConfidenceValue(association["confidence"]).value
        salience = SalienceValue(association["salience"]).value
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
                    strength=confidence,
                    observation_id=plan_ids.association_observation_ids[index],
                    observation_source="agent_explicit",
                    valence=confidence,
                    salience=salience,
                    evidence_refs=evidence_refs,
                ),
            )
        )
    return plan


def _required_structural_relation_id(
    plan_ids: CreatePlanIds, index: int
) -> str:
    """Return a preallocated structural relation id for problem-link effects."""

    try:
        return plan_ids.structural_relation_ids[index]
    except IndexError as exc:
        raise ValueError("create plan ids missing structural relation id") from exc
