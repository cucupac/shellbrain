"""This module defines bounded context-pack assembly with quotas, dedupe, and hard caps."""

from typing import Any

from shellbrain.boot.read_policy import resolve_read_limit, resolve_read_quotas


_BUCKET_ORDER = ("direct", "explicit", "implicit")
_SECTION_NAMES = {
    "direct": "direct",
    "explicit": "explicit_related",
    "implicit": "implicit_related",
}
_BUCKET_PRIORITY = {bucket_name: index for index, bucket_name in enumerate(_BUCKET_ORDER)}


def assemble_context_pack(scored_candidates: dict[str, list[dict[str, Any]]], payload: dict[str, Any]) -> dict[str, Any]:
    """This function assembles a final context pack from bucketed candidate groups."""

    mode = str(payload["mode"])
    limit = resolve_read_limit(mode=mode, explicit_limit=payload.get("limit"))
    quotas = resolve_read_quotas(mode=mode)
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
    """Normalize shellbrain kind values from entities or strings into JSON-safe text."""

    return str(getattr(kind, "value", kind))


def _assign_priorities(sections: dict[str, list[dict[str, Any]]]) -> None:
    """Assign one global priority order across displayed sections."""

    priority = 1
    for section_name in ("direct", "explicit_related", "implicit_related"):
        for item in sections[section_name]:
            item["priority"] = priority
            priority += 1
