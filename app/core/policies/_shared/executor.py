"""This module defines shared side-effect execution for create and update policies."""

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


def apply_side_effects(
    plan: list[dict[str, object]],
    uow: IUnitOfWork,
    *,
    embedding_provider: IEmbeddingProvider | None = None,
) -> None:
    """This function executes a deterministic side-effect plan inside one transaction."""

    for effect in plan:
        effect_type = str(effect["effect_type"])
        params = effect["params"]
        assert isinstance(params, dict)

        if effect_type == "memory.create":
            uow.memories.create(
                Memory(
                    id=str(params["memory_id"]),
                    repo_id=str(params["repo_id"]),
                    scope=MemoryScope(str(params["scope"])),
                    kind=MemoryKind(str(params["kind"])),
                    text=str(params["text"]),
                )
            )
            continue

        if effect_type == "memory_embedding.upsert":
            if embedding_provider is None:
                raise RuntimeError("Embedding provider is required for memory_embedding.upsert")
            uow.memories.upsert_embedding(
                memory_id=str(params["memory_id"]),
                model=str(params["model"]),
                vector=embedding_provider.embed(str(params["text"])),
            )
            continue

        if effect_type == "memory_evidence.attach":
            refs = params["refs"]
            assert isinstance(refs, list)
            for ref in refs:
                evidence = uow.evidence.upsert_ref(repo_id=str(params["repo_id"]), ref=str(ref))
                uow.evidence.link_memory_evidence(memory_id=str(params["memory_id"]), evidence_id=evidence.id)
            continue

        if effect_type == "problem_attempt.create":
            uow.experiences.create_problem_attempt(
                ProblemAttempt(
                    problem_id=str(params["problem_id"]),
                    attempt_id=str(params["attempt_id"]),
                    role=ProblemAttemptRole(str(params["role"])),
                )
            )
            continue

        if effect_type == "memory.archive_state":
            updated = uow.memories.set_archived(memory_id=str(params["memory_id"]), archived=bool(params["archived"]))
            if not updated:
                raise LookupError(f"Target shellbrain not found for archive update: {params['memory_id']}")
            continue

        if effect_type == "utility_observation.append":
            uow.utility.append_observation(
                UtilityObservation(
                    id=str(params["id"]),
                    memory_id=str(params["memory_id"]),
                    problem_id=str(params["problem_id"]),
                    vote=float(params["vote"]),
                    rationale=str(params["rationale"]) if params.get("rationale") is not None else None,
                )
            )
            continue

        if effect_type == "fact_update.create":
            uow.experiences.create_fact_update(
                FactUpdate(
                    id=str(params["id"]),
                    old_fact_id=str(params["old_fact_id"]),
                    change_id=str(params["change_id"]),
                    new_fact_id=str(params["new_fact_id"]),
                )
            )
            continue

        if effect_type == "association.upsert_and_observe":
            edge = uow.associations.upsert_edge(
                AssociationEdge(
                    id=str(params["edge_id"]),
                    repo_id=str(params["repo_id"]),
                    from_memory_id=str(params["from_memory_id"]),
                    to_memory_id=str(params["to_memory_id"]),
                    relation_type=AssociationRelationType(str(params["relation_type"])),
                    source_mode=AssociationSourceMode(str(params["source_mode"])),
                    state=AssociationState(str(params["state"])),
                    strength=float(params["strength"]),
                )
            )
            uow.associations.append_observation(
                AssociationObservation(
                    id=str(params["observation_id"]),
                    repo_id=str(params["repo_id"]),
                    edge_id=edge.id,
                    from_memory_id=str(params["from_memory_id"]),
                    to_memory_id=str(params["to_memory_id"]),
                    relation_type=AssociationRelationType(str(params["relation_type"])),
                    source=str(params["observation_source"]),
                    valence=float(params["valence"]),
                    salience=float(params["salience"]),
                )
            )
            evidence_refs = params.get("evidence_refs", [])
            assert isinstance(evidence_refs, list)
            for ref in evidence_refs:
                evidence = uow.evidence.upsert_ref(repo_id=str(params["repo_id"]), ref=str(ref))
                uow.evidence.link_association_edge_evidence(edge_id=edge.id, evidence_id=evidence.id)
            continue

        raise ValueError(f"Unsupported side effect type: {effect_type}")
