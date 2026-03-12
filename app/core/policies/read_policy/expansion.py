"""This module defines explicit and implicit expansion stage helpers for read policy."""

from typing import Any

from app.core.interfaces.repos import IReadPolicyRepo, ISemanticRetrievalRepo


def expand_candidates(
    direct_candidates: list[dict[str, Any]],
    payload: dict[str, Any],
    *,
    read_policy: IReadPolicyRepo,
    semantic_retrieval: ISemanticRetrievalRepo,
) -> dict[str, list[dict[str, Any]]]:
    """This function expands direct candidates via explicit links and semantic neighbors."""

    explicit: list[dict[str, Any]] = []
    implicit: list[dict[str, Any]] = []
    expand = payload.get("expand", {})
    repo_id = payload["repo_id"]
    include_global = payload.get("include_global", True)
    kinds = payload.get("kinds")
    min_strength = expand.get("min_association_strength", 0.25)
    semantic_hops = int(expand.get("semantic_hops", 0))

    for direct_candidate in direct_candidates:
        anchor_memory_id = direct_candidate["memory_id"]
        anchor_score = float(direct_candidate.get("rrf_score", direct_candidate.get("score", 0.0)))

        if expand.get("include_problem_links", True):
            for neighbor in read_policy.list_problem_attempt_neighbors(
                repo_id=repo_id,
                include_global=include_global,
                anchor_memory_id=anchor_memory_id,
                kinds=kinds,
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

        if expand.get("include_fact_update_links", True):
            for neighbor in read_policy.list_fact_update_neighbors(
                repo_id=repo_id,
                include_global=include_global,
                anchor_memory_id=anchor_memory_id,
                kinds=kinds,
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

        if expand.get("include_association_links", True):
            for neighbor in read_policy.list_association_neighbors(
                repo_id=repo_id,
                include_global=include_global,
                anchor_memory_id=anchor_memory_id,
                kinds=kinds,
                min_strength=min_strength,
            ):
                explicit.append(
                    {
                        "memory_id": neighbor["memory_id"],
                        "anchor_memory_id": anchor_memory_id,
                        "anchor_score": anchor_score,
                        "depth": 1,
                        "expansion_type": neighbor["expansion_type"],
                        "relation_strength": float(neighbor["strength"]),
                        "relation_type": neighbor["relation_type"],
                    }
                )

        if semantic_hops > 0:
            seen_memory_ids = {str(anchor_memory_id)}
            frontier = [str(anchor_memory_id)]
            for hop in range(1, semantic_hops + 1):
                next_frontier: list[str] = []
                for frontier_memory_id in frontier:
                    for neighbor in semantic_retrieval.list_semantic_neighbors(
                        repo_id=repo_id,
                        include_global=include_global,
                        anchor_memory_id=frontier_memory_id,
                        kinds=kinds,
                        limit=payload.get("limit"),
                    ):
                        neighbor_memory_id = str(neighbor["memory_id"])
                        if neighbor_memory_id in seen_memory_ids:
                            continue
                        seen_memory_ids.add(neighbor_memory_id)
                        next_frontier.append(neighbor_memory_id)
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
                frontier = next_frontier
                if not frontier:
                    break

    return {"explicit": explicit, "implicit": implicit}
