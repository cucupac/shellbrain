"""This module defines explicit and implicit expansion stage helpers for read policy."""

from typing import Any

from app.core.entities.settings import ReadPolicySettings, default_read_policy_settings
from app.core.interfaces.repos import IReadPolicyRepo, ISemanticRetrievalRepo


def expand_candidates(
    direct_candidates: list[dict[str, Any]],
    payload: dict[str, Any],
    *,
    read_policy: IReadPolicyRepo,
    semantic_retrieval: ISemanticRetrievalRepo,
    read_settings: ReadPolicySettings | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """This function expands direct candidates via explicit links and semantic neighbors."""

    read_settings = read_settings or default_read_policy_settings()
    payload = read_settings.resolve_payload_defaults(payload)
    explicit: list[dict[str, Any]] = []
    implicit: list[dict[str, Any]] = []
    expand = payload["expand"]
    repo_id = payload["repo_id"]
    include_global = bool(payload["include_global"])
    kinds = payload.get("kinds")
    min_strength = float(expand["min_association_strength"])
    semantic_hops = int(expand["semantic_hops"])
    max_association_depth = int(expand["max_association_depth"])

    for direct_candidate in direct_candidates:
        anchor_memory_id = direct_candidate["memory_id"]
        anchor_score = float(direct_candidate.get("rrf_score", direct_candidate.get("score", 0.0)))

        if expand["include_problem_links"]:
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

        if expand["include_fact_update_links"]:
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

        if expand["include_association_links"] and max_association_depth > 0:
            seen_association_memory_ids = {str(anchor_memory_id)}
            association_frontier = [str(anchor_memory_id)]
            for depth in range(1, max_association_depth + 1):
                next_association_frontier: list[str] = []
                for frontier_memory_id in association_frontier:
                    for neighbor in read_policy.list_association_neighbors(
                        repo_id=repo_id,
                        include_global=include_global,
                        anchor_memory_id=frontier_memory_id,
                        kinds=kinds,
                        min_strength=min_strength,
                    ):
                        neighbor_memory_id = str(neighbor["memory_id"])
                        if neighbor_memory_id in seen_association_memory_ids:
                            continue
                        seen_association_memory_ids.add(neighbor_memory_id)
                        next_association_frontier.append(neighbor_memory_id)
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
                association_frontier = next_association_frontier
                if not association_frontier:
                    break

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
