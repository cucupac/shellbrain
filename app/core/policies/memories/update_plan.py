"""This module defines pure update-policy planning helpers."""

from typing import Any

from app.core.use_cases.memories.effect_plan import (
    AssociationUpsertAndObserveEffectParams,
    EvidenceSourceEffectParams,
    StructuralFactChangeEffectParams,
    MemoryLifecycleUpdateEffectParams,
    PlannedEffect,
    UtilityObservationAppendEffectParams,
    make_side_effect,
)
from app.core.use_cases.memories.update.result import UpdatePlanIds
from app.core.entities.associations import AssociationSourceMode, AssociationState
from app.core.entities.memories import (
    ConfidenceValue,
    EvidenceRefs,
    SalienceValue,
    UtilityVoteValue,
)


def build_update_plan(
    payload: dict[str, Any], *, plan_ids: UpdatePlanIds
) -> list[PlannedEffect]:
    """This function converts a validated update payload into deterministic side effects."""

    update = payload["update"]
    update_type = update["type"]
    memory_id = payload["memory_id"]
    repo_id = payload["repo_id"]

    if update_type == "update_lifecycle":
        return [
            make_side_effect(
                "memory.lifecycle_update",
                MemoryLifecycleUpdateEffectParams(
                    event_id=_required(
                        plan_ids.memory_lifecycle_event_id,
                        "memory_lifecycle_event_id",
                    ),
                    repo_id=repo_id,
                    memory_id=memory_id,
                    status=update["status"],
                    rationale=update["rationale"],
                    actor=update["actor"],
                    validated_at=update.get("validated_at"),
                    superseded_by_id=update.get("superseded_by_id"),
                    evidence=tuple(
                        EvidenceSourceEffectParams(
                            kind=item["kind"],
                            ref=item.get("ref"),
                            episode_event_id=item.get("episode_event_id"),
                            anchor_id=item.get("anchor_id"),
                            memory_id=item.get("memory_id"),
                            commit_ref=item.get("commit_ref"),
                            transcript_ref=item.get("transcript_ref"),
                            note=item.get("note"),
                        )
                        for item in update["evidence"]
                    ),
                ),
            )
        ]

    if update_type == "utility_vote":
        evidence_refs = EvidenceRefs.optional(update.get("evidence_refs", [])).values
        return [
            make_side_effect(
                "utility_observation.append",
                UtilityObservationAppendEffectParams(
                    id=_required(
                        plan_ids.utility_observation_id, "utility_observation_id"
                    ),
                    repo_id=repo_id,
                    memory_id=memory_id,
                    problem_id=update["problem_id"],
                    vote=UtilityVoteValue(update["vote"]).value,
                    rationale=update.get("rationale"),
                    evidence_refs=evidence_refs,
                ),
            )
        ]

    if update_type == "fact_update_link":
        evidence_refs = EvidenceRefs.optional(update.get("evidence_refs", [])).values
        return [
            make_side_effect(
                "structural_fact_change.create",
                StructuralFactChangeEffectParams(
                    repo_id=repo_id,
                    old_fact_id=update["old_fact_id"],
                    change_id=memory_id,
                    new_fact_id=update["new_fact_id"],
                    structural_relation_ids=_required_structural_relation_ids(
                        plan_ids, count=3
                    ),
                    evidence_refs=evidence_refs,
                ),
            )
        ]

    if update_type == "association_link":
        confidence = ConfidenceValue(update["confidence"]).value
        salience = SalienceValue(update["salience"]).value
        evidence_refs = EvidenceRefs.required(update["evidence_refs"]).values
        return [
            make_side_effect(
                "association.upsert_and_observe",
                AssociationUpsertAndObserveEffectParams(
                    repo_id=repo_id,
                    edge_id=_required(
                        plan_ids.association_edge_id, "association_edge_id"
                    ),
                    from_memory_id=memory_id,
                    to_memory_id=update["to_memory_id"],
                    relation_type=update["relation_type"],
                    source_mode=AssociationSourceMode.AGENT.value,
                    state=AssociationState.TENTATIVE.value,
                    strength=confidence,
                    observation_id=_required(
                        plan_ids.association_observation_id,
                        "association_observation_id",
                    ),
                    observation_source="agent_explicit",
                    valence=confidence,
                    salience=salience,
                    evidence_refs=evidence_refs,
                ),
            )
        ]

    raise ValueError(f"Unsupported update type for plan build: {update_type}")


def _required(value: str | None, name: str) -> str:
    """Return one preallocated ID or fail when the use case omitted it."""

    if value is None:
        raise ValueError(f"update plan ids missing {name}")
    return value


def _required_structural_relation_ids(
    plan_ids: UpdatePlanIds, *, count: int
) -> tuple[str, str, str]:
    """Return the exact structural relation IDs required by a fact change."""

    if len(plan_ids.structural_relation_ids) != count:
        raise ValueError("update plan ids missing structural relation ids")
    first, second, third = plan_ids.structural_relation_ids
    return (first, second, third)
