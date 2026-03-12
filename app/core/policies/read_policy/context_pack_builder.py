"""This module defines bounded context-pack assembly with quotas, dedupe, and hard caps."""

from typing import Any

from app.boot.config import get_config_provider


_BUCKET_ORDER = ("direct", "explicit", "implicit")
_SECTION_NAMES = {
    "direct": "direct",
    "explicit": "explicit_related",
    "implicit": "implicit_related",
}
_BUCKET_PRIORITY = {bucket_name: index for index, bucket_name in enumerate(_BUCKET_ORDER)}


def assemble_context_pack(scored_candidates: dict[str, list[dict[str, Any]]], payload: dict[str, Any]) -> dict[str, Any]:
    """This function assembles a final context pack from bucketed candidate groups."""

    read_policy = get_config_provider().get_read_policy()
    mode = str(payload.get("mode", "targeted"))
    limit = _resolve_limit(payload, read_policy)
    quotas = _resolve_quotas(read_policy, mode)
    sorted_buckets = {
        bucket_name: sorted(
            scored_candidates.get(bucket_name, []),
            key=lambda item: (-float(item["score"]), str(item["memory_id"])),
        )
        for bucket_name in _BUCKET_ORDER
    }

    selected_by_bucket: dict[str, list[dict[str, Any]]] = {bucket_name: [] for bucket_name in _BUCKET_ORDER}
    seen_memory_ids: set[str] = set()
    spill_pool: list[tuple[str, dict[str, Any]]] = []
    remaining = limit

    for bucket_name in _BUCKET_ORDER:
        section_quota = min(int(quotas.get(bucket_name, 0)), remaining)
        selected_count = 0
        for candidate in sorted_buckets[bucket_name]:
            memory_id = str(candidate["memory_id"])
            if memory_id in seen_memory_ids:
                continue
            if selected_count < section_quota:
                seen_memory_ids.add(memory_id)
                selected_by_bucket[bucket_name].append(candidate)
                selected_count += 1
                remaining -= 1
            else:
                spill_pool.append((bucket_name, candidate))

    if remaining > 0:
        spill_pool.sort(
            key=lambda item: (
                -float(item[1]["score"]),
                _BUCKET_PRIORITY[item[0]],
                str(item[1]["memory_id"]),
            )
        )
        for bucket_name, candidate in spill_pool:
            if remaining <= 0:
                break
            memory_id = str(candidate["memory_id"])
            if memory_id in seen_memory_ids:
                continue
            seen_memory_ids.add(memory_id)
            selected_by_bucket[bucket_name].append(candidate)
            remaining -= 1

    sections = {
        "direct": [_shape_item(candidate, "direct") for candidate in selected_by_bucket["direct"]],
        "explicit_related": [_shape_item(candidate, "explicit") for candidate in selected_by_bucket["explicit"]],
        "implicit_related": [_shape_item(candidate, "implicit") for candidate in selected_by_bucket["implicit"]],
    }
    _assign_priorities(sections)
    return {
        "meta": {
            "mode": mode,
            "query": payload.get("query"),
            "limit": limit,
            "counts": {
                "direct": len(sections["direct"]),
                "explicit_related": len(sections["explicit_related"]),
                "implicit_related": len(sections["implicit_related"]),
            },
        },
        "direct": sections["direct"],
        "explicit_related": sections["explicit_related"],
        "implicit_related": sections["implicit_related"],
    }


def _resolve_limit(payload: dict[str, Any], read_policy: dict[str, Any]) -> int:
    """Resolve the effective context-pack limit for the current read mode."""

    explicit_limit = payload.get("limit")
    if explicit_limit is not None:
        return int(explicit_limit)
    mode = str(payload.get("mode", "targeted"))
    limits = read_policy.get("limits") or {}
    return int(limits.get(mode, 20))


def _resolve_quotas(read_policy: dict[str, Any], mode: str) -> dict[str, int]:
    """Resolve the per-bucket selection quotas for one read mode."""

    quotas = (read_policy.get("quotas") or {}).get(mode) or {}
    return {
        "direct": int(quotas.get("direct", 0)),
        "explicit": int(quotas.get("explicit", 0)),
        "implicit": int(quotas.get("implicit", 0)),
    }


def _shape_item(candidate: dict[str, Any], bucket_name: str) -> dict[str, Any]:
    """Project one internal candidate into the compact LLM-facing item shape."""

    item: dict[str, Any] = {
        "memory_id": str(candidate["memory_id"]),
        "why_included": _resolve_why_included(candidate, bucket_name),
    }
    if "kind" in candidate:
        item["kind"] = _normalize_kind(candidate["kind"])
    if "text" in candidate:
        item["text"] = str(candidate["text"])
    if bucket_name != "direct" and "anchor_memory_id" in candidate:
        item["anchor_memory_id"] = str(candidate["anchor_memory_id"])
    if "relation_type" in candidate:
        item["relation_type"] = str(candidate["relation_type"])
    return item


def _resolve_why_included(candidate: dict[str, Any], bucket_name: str) -> str:
    """Resolve a stable user-facing inclusion reason from candidate metadata."""

    if "why_included" in candidate:
        return str(candidate["why_included"])
    if bucket_name == "direct":
        return "direct_match"
    if bucket_name == "implicit":
        return "semantic_neighbor"
    expansion_type = str(candidate.get("expansion_type", ""))
    return {
        "problem_attempt": "problem_attempt",
        "fact_update": "fact_update",
        "association": "association_link",
    }.get(expansion_type, expansion_type or "related_memory")


def _normalize_kind(kind: Any) -> str:
    """Normalize memory kind values from entities or strings into JSON-safe text."""

    return str(getattr(kind, "value", kind))


def _assign_priorities(sections: dict[str, list[dict[str, Any]]]) -> None:
    """Assign one global priority order across displayed sections."""

    priority = 1
    for section_name in ("direct", "explicit_related", "implicit_related"):
        for item in sections[section_name]:
            item["priority"] = priority
            priority += 1
