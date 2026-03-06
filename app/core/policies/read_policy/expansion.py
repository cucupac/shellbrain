"""This module defines explicit and implicit expansion stage helpers for read policy."""

from typing import Any

from app.core.interfaces.repos import IReadPolicyRepo


def expand_candidates(
    direct_candidates: list[dict[str, Any]],
    payload: dict[str, Any],
    *,
    read_policy: IReadPolicyRepo,
) -> dict[str, list[dict[str, Any]]]:
    """This function expands direct candidates via explicit links and semantic neighbors."""

    explicit: list[dict[str, Any]] = []
    expand = payload.get("expand", {})
    repo_id = payload["repo_id"]
    include_global = payload.get("include_global", True)
    kinds = payload.get("kinds")
    min_strength = expand.get("min_association_strength", 0.25)

    for direct_candidate in direct_candidates:
        anchor_memory_id = direct_candidate["memory_id"]
        anchor_score = float(direct_candidate["score"])

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
                        "expansion_type": neighbor["expansion_type"],
                        "score": anchor_score,
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
                        "expansion_type": neighbor["expansion_type"],
                        "score": anchor_score,
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
                        "expansion_type": neighbor["expansion_type"],
                        "score": anchor_score * float(neighbor["strength"]),
                    }
                )

    return {"explicit": explicit, "implicit": []}
