"""This module defines bounded context-pack assembly with quotas, dedupe, and hard caps."""

from typing import Any


def assemble_context_pack(scored_candidates: dict[str, list[dict[str, Any]]], payload: dict[str, Any]) -> dict[str, Any]:
    """This function assembles a final context pack from bucketed candidate groups."""

    limit = payload.get("limit", 20)
    items: list[dict[str, Any]] = []
    seen_memory_ids: set[str] = set()

    for bucket_name in ("direct", "explicit", "implicit"):
        bucket = sorted(
            scored_candidates.get(bucket_name, []),
            key=lambda item: (-float(item["score"]), str(item["memory_id"])),
        )
        for candidate in bucket:
            memory_id = str(candidate["memory_id"])
            if memory_id in seen_memory_ids:
                continue
            seen_memory_ids.add(memory_id)
            items.append({"memory_id": memory_id})
            if len(items) >= limit:
                return {"items": items}

    return {"items": items}
