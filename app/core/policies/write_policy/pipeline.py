"""This module defines write-policy pipeline orchestration for create and update requests."""

from uuid import uuid4
from typing import Any

from app.core.entities.associations import (
    AssociationEdge,
    AssociationObservation,
    AssociationRelationType,
    AssociationSourceMode,
    AssociationState,
)
from app.core.entities.facts import FactUpdate, ProblemAttempt, ProblemAttemptRole
from app.core.entities.memory import Memory, MemoryKind, MemoryScope
from app.core.entities.utility import UtilityObservation
from app.core.interfaces.embeddings import IEmbeddingProvider
from app.core.interfaces.unit_of_work import IUnitOfWork
from app.core.policies.write_policy.side_effects import make_memory_create_effect, make_memory_evidence_effect, make_side_effect

def build_write_plan(payload: dict[str, Any], *, embedding_model: str = "unknown") -> list[dict[str, Any]]:
    """This function converts a validated payload into deterministic write side effects."""

    op = payload.get("op")
    if op == "create":
        return _build_create_plan(payload, embedding_model=embedding_model)
    if op == "update":
        return _build_update_plan(payload)
    raise ValueError(f"Unsupported write operation for plan build: {op}")


def apply_write_plan(plan: list[dict[str, Any]], uow: IUnitOfWork, *, embedding_provider: IEmbeddingProvider | None = None) -> None:
    """This function executes a deterministic write plan using repository interfaces inside one transaction."""

    for effect in plan:
        effect_type = effect["effect_type"]
        params = effect["params"]
        if effect_type == "memory.create":
            uow.memories.create(
                Memory(
                    id=params["memory_id"],
                    repo_id=params["repo_id"],
                    scope=MemoryScope(params["scope"]),
                    kind=MemoryKind(params["kind"]),
                    text=params["text"],
                    create_confidence=params["confidence"],
                )
            )
            continue

        if effect_type == "memory_embedding.upsert":
            if embedding_provider is None:
                raise RuntimeError("Embedding provider is required for memory_embedding.upsert")
            uow.memories.upsert_embedding(
                memory_id=params["memory_id"],
                model=params["model"],
                vector=embedding_provider.embed(params["text"]),
            )
            continue

        if effect_type == "memory_evidence.attach":
            for ref in params["refs"]:
                evidence = uow.evidence.upsert_ref(repo_id=params["repo_id"], ref=ref)
                uow.evidence.link_memory_evidence(memory_id=params["memory_id"], evidence_id=evidence.id)
            continue

        if effect_type == "problem_attempt.create":
            uow.experiences.create_problem_attempt(
                ProblemAttempt(
                    problem_id=params["problem_id"],
                    attempt_id=params["attempt_id"],
                    role=ProblemAttemptRole(params["role"]),
                )
            )
            continue

        if effect_type == "memory.archive_state":
            updated = uow.memories.set_archived(memory_id=params["memory_id"], archived=params["archived"])
            if not updated:
                raise LookupError(f"Target memory not found for archive update: {params['memory_id']}")
            continue

        if effect_type == "utility_observation.append":
            uow.utility.append_observation(
                UtilityObservation(
                    id=params["id"],
                    memory_id=params["memory_id"],
                    problem_id=params["problem_id"],
                    vote=params["vote"],
                    rationale=params.get("rationale"),
                )
            )
            continue

        if effect_type == "fact_update.create":
            uow.experiences.create_fact_update(
                FactUpdate(
                    id=params["id"],
                    old_fact_id=params["old_fact_id"],
                    change_id=params["change_id"],
                    new_fact_id=params["new_fact_id"],
                )
            )
            continue

        if effect_type == "association.upsert_and_observe":
            edge = uow.associations.upsert_edge(
                AssociationEdge(
                    id=params["edge_id"],
                    repo_id=params["repo_id"],
                    from_memory_id=params["from_memory_id"],
                    to_memory_id=params["to_memory_id"],
                    relation_type=AssociationRelationType(params["relation_type"]),
                    source_mode=AssociationSourceMode(params["source_mode"]),
                    state=AssociationState(params["state"]),
                    strength=params["strength"],
                )
            )
            uow.associations.append_observation(
                AssociationObservation(
                    id=params["observation_id"],
                    repo_id=params["repo_id"],
                    edge_id=edge.id,
                    from_memory_id=params["from_memory_id"],
                    to_memory_id=params["to_memory_id"],
                    relation_type=AssociationRelationType(params["relation_type"]),
                    source=params["observation_source"],
                    valence=params["valence"],
                    salience=params["salience"],
                )
            )
            for ref in params.get("evidence_refs", []):
                evidence = uow.evidence.upsert_ref(repo_id=params["repo_id"], ref=ref)
                uow.evidence.link_association_edge_evidence(edge_id=edge.id, evidence_id=evidence.id)
            continue

        raise ValueError(f"Unsupported write side effect type: {effect_type}")


def _build_create_plan(payload: dict[str, Any], *, embedding_model: str) -> list[dict[str, Any]]:
    """This function builds the deterministic create side-effect plan from validated payload fields."""

    memory = payload["memory"]
    repo_id = payload["repo_id"]
    memory_id = payload["memory_id"]
    plan: list[dict[str, Any]] = [
        make_memory_create_effect(
            memory_id=memory_id,
            repo_id=repo_id,
            scope=memory["scope"],
            kind=memory["kind"],
            text=memory["text"],
            confidence=memory.get("confidence"),
        ),
        make_side_effect(
            "memory_embedding.upsert",
            {
                "memory_id": memory_id,
                "model": embedding_model,
                "text": memory["text"],
            },
        ),
        make_memory_evidence_effect(memory_id=memory_id, repo_id=repo_id, refs=list(memory["evidence_refs"])),
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
                    "salience": association.get("salience", 0.5),
                    "evidence_refs": list(memory["evidence_refs"]),
                },
            )
        )
    return plan


def _build_update_plan(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """This function builds the deterministic update side-effect plan from validated payload fields."""

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
                    "salience": update.get("salience", 0.5),
                    "evidence_refs": list(update.get("evidence_refs", [])),
                },
            )
        ]

    raise ValueError(f"Unsupported update side-effect mapping: {update_type}")
