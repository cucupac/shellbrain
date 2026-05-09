"""This module defines pure update-policy planning helpers."""

from typing import Any

from app.core.contracts.planned_effects import (
    AssociationUpsertAndObserveEffectParams,
    FactUpdateCreateEffectParams,
    MemoryArchiveStateEffectParams,
    PlannedEffect,
    UpdatePlanIds,
    UtilityObservationAppendEffectParams,
    make_side_effect,
)
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

    if update_type == "archive_state":
        return [
            make_side_effect(
                "memory.archive_state",
                MemoryArchiveStateEffectParams(
                    memory_id=memory_id, archived=update["archived"]
                ),
            )
        ]

    if update_type == "utility_vote":
        return [
            make_side_effect(
                "utility_observation.append",
                UtilityObservationAppendEffectParams(
                    id=_required(
                        plan_ids.utility_observation_id, "utility_observation_id"
                    ),
                    memory_id=memory_id,
                    problem_id=update["problem_id"],
                    vote=UtilityVoteValue(update["vote"]).value,
                    rationale=update.get("rationale"),
                ),
            )
        ]

    if update_type == "fact_update_link":
        return [
            make_side_effect(
                "fact_update.create",
                FactUpdateCreateEffectParams(
                    id=_required(plan_ids.fact_update_id, "fact_update_id"),
                    old_fact_id=update["old_fact_id"],
                    change_id=memory_id,
                    new_fact_id=update["new_fact_id"],
                ),
            )
        ]

    if update_type == "association_link":
        confidence = ConfidenceValue.from_optional(update.get("confidence")).value
        salience = SalienceValue.from_optional(update.get("salience")).value
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
