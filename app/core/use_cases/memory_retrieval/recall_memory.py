"""This module defines the minimal Phase 1 recall orchestration entry point."""

from __future__ import annotations

from typing import Any

from app.core.contracts.requests import MemoryReadRequest, MemoryRecallRequest
from app.core.contracts.responses import OperationResult
from app.core.entities.settings import ReadPolicySettings, ThresholdSettings, default_read_policy_settings, default_threshold_settings
from app.core.interfaces.unit_of_work import IUnitOfWork
from app.core.use_cases.memory_retrieval.read_memory import execute_read_memory


def execute_recall_memory(
    request: MemoryRecallRequest,
    uow: IUnitOfWork,
    *,
    read_settings: ReadPolicySettings | None = None,
    threshold_settings: ThresholdSettings | None = None,
) -> OperationResult:
    """Run targeted read retrieval and return a deterministic recall brief."""

    read_settings = read_settings or default_read_policy_settings()
    threshold_settings = threshold_settings or default_threshold_settings()
    read_request = MemoryReadRequest(
        repo_id=request.repo_id,
        mode="targeted",
        query=request.query,
        limit=request.limit,
    )
    try:
        read_result = execute_read_memory(
            read_request,
            uow,
            read_settings=read_settings,
            threshold_settings=threshold_settings,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        read_result = execute_read_memory(read_request, uow)
    pack = read_result.data.get("pack", {})
    if not isinstance(pack, dict):
        pack = {}

    source_items = _source_items_from_pack(pack)
    fallback_reason = None if source_items else "no_candidates"
    brief = {
        "summary": _summary_text(source_count=len(source_items), fallback_reason=fallback_reason),
        "sources": [
            {
                "kind": item["source_kind"],
                "id": item["source_id"],
                "section": item["input_section"],
            }
            for item in source_items
            if item["output_section"] is not None
        ],
    }

    return OperationResult(
        status="ok",
        data={
            "brief": brief,
            "fallback_reason": fallback_reason,
            "_telemetry": {
                "candidate_pack": pack,
                "source_items": source_items,
            },
        },
    )


def _source_items_from_pack(pack: dict[str, Any]) -> list[dict[str, Any]]:
    """Build stable candidate provenance rows from one read pack."""

    items: list[dict[str, Any]] = []
    ordinal = 1
    for input_section, bucket_name in (
        ("direct", "direct"),
        ("explicit_related", "explicit_related"),
        ("implicit_related", "implicit_related"),
    ):
        bucket = pack.get(bucket_name)
        if not isinstance(bucket, list):
            continue
        for item in bucket:
            if not isinstance(item, dict) or "memory_id" not in item:
                continue
            items.append(
                {
                    "ordinal": ordinal,
                    "source_kind": "memory",
                    "source_id": str(item["memory_id"]),
                    "input_section": input_section,
                    "output_section": "sources",
                }
            )
            ordinal += 1

    concepts = pack.get("concepts")
    if isinstance(concepts, dict) and isinstance(concepts.get("items"), list):
        for item in concepts["items"]:
            if not isinstance(item, dict):
                continue
            source_id = item.get("id") or item.get("ref")
            if source_id is None:
                continue
            items.append(
                {
                    "ordinal": ordinal,
                    "source_kind": "concept",
                    "source_id": str(source_id),
                    "input_section": "concept_orientation",
                    "output_section": "sources",
                }
            )
            ordinal += 1
    return items


def _summary_text(*, source_count: int, fallback_reason: str | None) -> str:
    """Return deterministic stub recall summary text."""

    if fallback_reason == "no_candidates":
        return "No stored Shellbrain context matched this recall query."
    return f"Shellbrain found {source_count} recall source(s) for this query."
