"""This module defines update-policy planning and execution helpers."""

from uuid import uuid4
from typing import Any

from app.core.entities.associations import AssociationSourceMode, AssociationState
from app.core.interfaces.unit_of_work import IUnitOfWork
from app.core.policies._shared.executor import apply_side_effects
from app.core.policies._shared.side_effects import make_side_effect


def build_update_plan(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """This function converts a validated update payload into deterministic side effects."""

    update = payload["update"]
    update_type = update["type"]
    memory_id = payload["memory_id"]
    repo_id = payload["repo_id"]

    if update_type == "archive_state":
        return [make_side_effect("memory.archive_state", {"memory_id": memory_id, "archived": update["archived"]})]

    if update_type == "utility_vote":
        return [
            make_side_effect(
                "utility_observation.append",
                {
                    "id": str(uuid4()),
                    "memory_id": memory_id,
                    "problem_id": update["problem_id"],
                    "vote": update["vote"],
                    "rationale": update.get("rationale"),
                },
            )
        ]

    if update_type == "fact_update_link":
        return [
            make_side_effect(
                "fact_update.create",
                {
                    "id": str(uuid4()),
                    "old_fact_id": update["old_fact_id"],
                    "change_id": memory_id,
                    "new_fact_id": update["new_fact_id"],
                },
            )
        ]

    if update_type == "association_link":
        confidence = update.get("confidence")
        salience = update.get("salience")
        return [
            make_side_effect(
                "association.upsert_and_observe",
                {
                    "repo_id": repo_id,
                    "edge_id": str(uuid4()),
                    "from_memory_id": memory_id,
                    "to_memory_id": update["to_memory_id"],
                    "relation_type": update["relation_type"],
                    "source_mode": AssociationSourceMode.AGENT.value,
                    "state": AssociationState.TENTATIVE.value,
                    "strength": confidence if confidence is not None else 0.5,
                    "observation_id": str(uuid4()),
                    "observation_source": "agent_explicit",
                    "valence": confidence if confidence is not None else 0.5,
                    "salience": salience if salience is not None else 0.5,
                    "evidence_refs": list(update["evidence_refs"]),
                },
            )
        ]

    raise ValueError(f"Unsupported update type for plan build: {update_type}")


def apply_update_plan(plan: list[dict[str, Any]], uow: IUnitOfWork) -> None:
    """This function executes a deterministic update plan inside one transaction."""

    apply_side_effects(plan, uow)
