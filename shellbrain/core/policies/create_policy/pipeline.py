"""This module defines create-policy planning and execution helpers."""

from uuid import uuid4
from typing import Any

from shellbrain.core.entities.associations import AssociationSourceMode, AssociationState
from shellbrain.core.entities.memory import MemoryKind
from shellbrain.core.interfaces.embeddings import IEmbeddingProvider
from shellbrain.core.interfaces.unit_of_work import IUnitOfWork
from shellbrain.core.policies._shared.executor import apply_side_effects
from shellbrain.core.policies._shared.side_effects import make_side_effect


def build_create_plan(payload: dict[str, Any], *, embedding_model: str = "unknown") -> list[dict[str, Any]]:
    """This function converts a validated create payload into deterministic side effects."""

    memory = payload["memory"]
    repo_id = payload["repo_id"]
    memory_id = payload["memory_id"]
    plan: list[dict[str, Any]] = [
        make_side_effect(
            "memory.create",
            {
                "memory_id": memory_id,
                "repo_id": repo_id,
                "scope": memory["scope"],
                "kind": memory["kind"],
                "text": memory["text"],
            },
        ),
        make_side_effect(
            "memory_embedding.upsert",
            {
                "memory_id": memory_id,
                "model": embedding_model,
                "text": memory["text"],
            },
        ),
        make_side_effect(
            "memory_evidence.attach",
            {
                "memory_id": memory_id,
                "repo_id": repo_id,
                "refs": list(memory["evidence_refs"]),
            },
        ),
    ]

    problem_id = (memory.get("links") or {}).get("problem_id")
    if memory["kind"] in {MemoryKind.SOLUTION.value, MemoryKind.FAILED_TACTIC.value} and problem_id:
        plan.append(
            make_side_effect(
                "problem_attempt.create",
                {
                    "problem_id": problem_id,
                    "attempt_id": memory_id,
                    "role": memory["kind"],
                },
            )
        )

    for association in (memory.get("links") or {}).get("associations", []):
        confidence = association.get("confidence")
        salience = association.get("salience")
        plan.append(
            make_side_effect(
                "association.upsert_and_observe",
                {
                    "repo_id": repo_id,
                    "edge_id": str(uuid4()),
                    "from_memory_id": memory_id,
                    "to_memory_id": association["to_memory_id"],
                    "relation_type": association["relation_type"],
                    "source_mode": AssociationSourceMode.AGENT.value,
                    "state": AssociationState.TENTATIVE.value,
                    "strength": confidence if confidence is not None else 0.5,
                    "observation_id": str(uuid4()),
                    "observation_source": "agent_explicit",
                    "valence": confidence if confidence is not None else 0.5,
                    "salience": salience if salience is not None else 0.5,
                    "evidence_refs": list(memory["evidence_refs"]),
                },
            )
        )
    return plan


def apply_create_plan(
    plan: list[dict[str, Any]],
    uow: IUnitOfWork,
    *,
    embedding_provider: IEmbeddingProvider,
) -> None:
    """This function executes a deterministic create plan inside one transaction."""

    apply_side_effects(plan, uow, embedding_provider=embedding_provider)
