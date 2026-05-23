"""This module defines explicit and implicit expansion stage helpers for read policy."""

from typing import Any

from app.core.entities.settings import ReadPolicySettings, default_read_policy_settings
from app.core.ports.db.retrieval_repositories import (
    IReadPolicyRepo,
    ISemanticRetrievalRepo,
)
from app.core.policies.retrieval.expansion import (
    select_association_neighbors,
    select_structural_memory_relation_neighbors,
)
from app.core.policies.retrieval.ontology_semantics import (
    STRUCTURAL_FACT_UPDATE_RELATION_PREDICATES,
    STRUCTURAL_PROBLEM_RELATION_PREDICATES,
)


def expand_candidates(
    direct_candidates: list[dict[str, Any]],
    request_data: dict[str, Any],
    *,
    read_policy: IReadPolicyRepo,
    semantic_retrieval: ISemanticRetrievalRepo,
    read_settings: ReadPolicySettings | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """This function expands direct candidates via explicit links and semantic neighbors."""

    read_settings = read_settings or default_read_policy_settings()
    request_data = read_settings.resolve_payload_defaults(request_data)
    explicit: list[dict[str, Any]] = []
    implicit: list[dict[str, Any]] = []
    expand = request_data["expand"]
    repo_id = request_data["repo_id"]
    include_global = bool(request_data["include_global"])
    kinds = request_data.get("kinds")
    min_strength = float(expand["min_association_strength"])
    semantic_hops = int(expand["semantic_hops"])
    max_association_depth = int(expand["max_association_depth"])

    for direct_candidate in direct_candidates:
        anchor_memory_id = direct_candidate["memory_id"]
        anchor_score = _candidate_anchor_score(direct_candidate)

        if expand["include_problem_links"]:
            for neighbor in select_structural_memory_relation_neighbors(
                read_policy.list_structural_memory_relation_rows(
                    repo_id=repo_id,
                    include_global=include_global,
                    anchor_memory_id=anchor_memory_id,
                    kinds=kinds,
                    predicates=STRUCTURAL_PROBLEM_RELATION_PREDICATES,
                ),
                anchor_memory_id=anchor_memory_id,
            ):
                explicit.append(
                    {
                        "memory_id": neighbor["memory_id"],
                        "anchor_memory_id": anchor_memory_id,
                        "anchor_score": anchor_score,
                        "depth": 1,
                        "expansion_type": neighbor["expansion_type"],
                    }
                )
        if expand["include_fact_update_links"]:
            for neighbor in select_structural_memory_relation_neighbors(
                read_policy.list_structural_memory_relation_rows(
                    repo_id=repo_id,
                    include_global=include_global,
                    anchor_memory_id=anchor_memory_id,
                    kinds=kinds,
                    predicates=STRUCTURAL_FACT_UPDATE_RELATION_PREDICATES,
                ),
                anchor_memory_id=anchor_memory_id,
            ):
                explicit.append(
                    {
                        "memory_id": neighbor["memory_id"],
                        "anchor_memory_id": anchor_memory_id,
                        "anchor_score": anchor_score,
                        "depth": 1,
                        "expansion_type": neighbor["expansion_type"],
                    }
                )
        if expand["include_association_links"] and max_association_depth > 0:
            seen_association_memory_ids = {str(anchor_memory_id)}
            association_queue = [str(anchor_memory_id)]
            for depth in range(1, max_association_depth + 1):
                next_association_queue: list[str] = []
                for queued_memory_id in association_queue:
                    edge_rows = read_policy.list_association_edge_rows(
                        repo_id=repo_id,
                        include_global=include_global,
                        anchor_memory_id=queued_memory_id,
                        kinds=kinds,
                    )
                    for neighbor in select_association_neighbors(
                        edge_rows,
                        anchor_memory_id=queued_memory_id,
                        min_strength=min_strength,
                    ):
                        neighbor_memory_id = str(neighbor["memory_id"])
                        if neighbor_memory_id in seen_association_memory_ids:
                            continue
                        seen_association_memory_ids.add(neighbor_memory_id)
                        next_association_queue.append(neighbor_memory_id)
                        explicit.append(
                            {
                                "memory_id": neighbor_memory_id,
                                "anchor_memory_id": anchor_memory_id,
                                "anchor_score": anchor_score,
                                "depth": depth,
                                "expansion_type": neighbor["expansion_type"],
                                "relation_strength": float(neighbor["strength"]),
                                "relation_type": neighbor["relation_type"],
                            }
                        )
                association_queue = next_association_queue
                if not association_queue:
                    break

        if semantic_hops > 0:
            seen_memory_ids = {str(anchor_memory_id)}
            semantic_queue = [str(anchor_memory_id)]
            for hop in range(1, semantic_hops + 1):
                next_semantic_queue: list[str] = []
                for queued_memory_id in semantic_queue:
                    for neighbor in semantic_retrieval.list_semantic_neighbors(
                        repo_id=repo_id,
                        include_global=include_global,
                        anchor_memory_id=queued_memory_id,
                        kinds=kinds,
                        limit=request_data.get("limit"),
                    ):
                        neighbor_memory_id = str(neighbor["memory_id"])
                        if neighbor_memory_id in seen_memory_ids:
                            continue
                        seen_memory_ids.add(neighbor_memory_id)
                        next_semantic_queue.append(neighbor_memory_id)
                        implicit.append(
                            {
                                "memory_id": neighbor_memory_id,
                                "anchor_memory_id": anchor_memory_id,
                                "anchor_score": anchor_score,
                                "hop": hop,
                                "expansion_type": "semantic_neighbor",
                                "neighbor_similarity": float(neighbor["score"]),
                            }
                        )
                semantic_queue = next_semantic_queue
                if not semantic_queue:
                    break

    return {"explicit": explicit, "implicit": implicit}


def _candidate_anchor_score(candidate: dict[str, Any]) -> float:
    """Return the explicit score field carried by a direct read candidate."""

    if "rrf_score" in candidate:
        return float(candidate["rrf_score"])
    if "score" in candidate:
        return float(candidate["score"])
    raise ValueError(
        f"Direct candidate {candidate.get('memory_id')} is missing a score for expansion"
    )
