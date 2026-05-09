"""Read telemetry record builders."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from app.core.contracts.retrieval import MemoryReadRequest
from app.infrastructure.telemetry.records import (
    ReadResultItemRecord,
    ReadSummaryRecord,
)

__all__ = ["build_read_summary_records", "estimate_read_pack_size"]


def build_read_summary_records(
    *,
    invocation_id: str,
    requested_limit: int | None,
    request: MemoryReadRequest,
    pack: dict[str, Any],
    created_at: datetime,
) -> tuple[ReadSummaryRecord, list[ReadResultItemRecord]]:
    """Build one read summary row and one item row per displayed memory."""

    direct = list(pack.get("direct", []))
    explicit_related = list(pack.get("explicit_related", []))
    implicit_related = list(pack.get("implicit_related", []))
    items: list[ReadResultItemRecord] = []
    ordinal = 1
    for section_name, bucket in (
        ("direct", direct),
        ("explicit_related", explicit_related),
        ("implicit_related", implicit_related),
    ):
        for item in bucket:
            items.append(
                ReadResultItemRecord(
                    invocation_id=invocation_id,
                    ordinal=ordinal,
                    memory_id=str(item["memory_id"]),
                    kind=str(item["kind"]),
                    section=section_name,
                    priority=ordinal,
                    why_included=str(item.get("why_included") or ""),
                    anchor_memory_id=_optional_string(item.get("anchor_memory_id")),
                    relation_type=_optional_string(item.get("relation_type")),
                )
            )
            ordinal += 1

    pack_size = estimate_read_pack_size(pack=pack)

    summary = ReadSummaryRecord(
        invocation_id=invocation_id,
        query_text=request.query,
        mode=request.mode,
        requested_limit=requested_limit,
        effective_limit=int(request.limit or len(items) or 0),
        include_global=request.include_global,
        kinds_filter=list(request.kinds) if request.kinds is not None else None,
        direct_count=len(direct),
        explicit_related_count=len(explicit_related),
        implicit_related_count=len(implicit_related),
        total_returned=len(items),
        zero_results=len(items) == 0,
        pack_char_count=int(pack_size["pack_char_count"]),
        pack_token_estimate=int(pack_size["pack_token_estimate"]),
        pack_token_estimate_method=str(pack_size["pack_token_estimate_method"]),
        direct_token_estimate=int(pack_size["direct_token_estimate"]),
        explicit_related_token_estimate=int(
            pack_size["explicit_related_token_estimate"]
        ),
        implicit_related_token_estimate=int(
            pack_size["implicit_related_token_estimate"]
        ),
        concept_count=int(pack_size["concept_count"]),
        concept_token_estimate=int(pack_size["concept_token_estimate"]),
        concept_refs_returned=list(pack_size["concept_refs_returned"]),
        concept_facets_returned=list(pack_size["concept_facets_returned"]),
        created_at=created_at,
    )
    return summary, items


def estimate_read_pack_size(
    *, pack: dict[str, Any]
) -> dict[str, int | str | list[str]]:
    """Estimate one read-pack footprint with one stable local heuristic."""

    serialized_pack = _compact_json(pack)
    return {
        "pack_char_count": len(serialized_pack),
        "pack_token_estimate": _estimate_tokens_from_text(serialized_pack),
        "pack_token_estimate_method": "json_compact_chars_div4_v1",
        "direct_token_estimate": _estimate_section_tokens(pack.get("direct")),
        "explicit_related_token_estimate": _estimate_section_tokens(
            pack.get("explicit_related")
        ),
        "implicit_related_token_estimate": _estimate_section_tokens(
            pack.get("implicit_related")
        ),
        "concept_count": _concept_count(pack.get("concepts")),
        "concept_token_estimate": _estimate_section_tokens(pack.get("concepts")),
        "concept_refs_returned": _concept_refs(pack.get("concepts")),
        "concept_facets_returned": _concept_facets(pack.get("concepts")),
    }


def _optional_string(value: object) -> str | None:
    """Return a string value or None when the field is absent."""

    return str(value) if isinstance(value, str) else None


def _estimate_section_tokens(section: Any) -> int:
    """Estimate tokens for one pack section while treating empty sections as zero."""

    if isinstance(section, list) and not section:
        return 0
    if section in (None, {}):
        return 0
    return _estimate_tokens_from_text(_compact_json(section))


def _concept_count(section: Any) -> int:
    """Return the number of concept items in one concept pack section."""

    if not isinstance(section, dict):
        return 0
    items = section.get("items")
    return len(items) if isinstance(items, list) else 0


def _concept_refs(section: Any) -> list[str]:
    """Return concept refs rendered in one concept pack section."""

    if not isinstance(section, dict):
        return []
    items = section.get("items")
    if not isinstance(items, list):
        return []
    return [
        str(item["ref"]) for item in items if isinstance(item, dict) and "ref" in item
    ]


def _concept_facets(section: Any) -> list[str]:
    """Return requested concept facets rendered in one concept pack section."""

    if not isinstance(section, dict):
        return []
    facets: set[str] = set()
    items = section.get("items")
    if not isinstance(items, list):
        return []
    for item in items:
        if not isinstance(item, dict):
            continue
        for facet in ("claims", "relations", "groundings", "memory_links", "evidence"):
            if facet in item:
                facets.add(facet)
    return sorted(facets)


def _estimate_tokens_from_text(text: str) -> int:
    """Return one stable local token estimate from compact text length."""

    if not text:
        return 0
    return (len(text) + 3) // 4


def _compact_json(value: Any) -> str:
    """Render one deterministic compact JSON string for token estimation."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
