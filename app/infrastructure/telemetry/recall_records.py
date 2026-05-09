"""Recall telemetry record builders."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.contracts.retrieval import MemoryRecallRequest
from app.infrastructure.telemetry.read_records import (
    _compact_json,
    _estimate_tokens_from_text,
    _optional_string,
    estimate_read_pack_size,
)
from app.infrastructure.telemetry.records import (
    RecallSourceItemRecord,
    RecallSummaryRecord,
)

__all__ = ["build_recall_summary_records"]


def build_recall_summary_records(
    *,
    invocation_id: str,
    request: MemoryRecallRequest,
    recall_telemetry: dict[str, Any],
    brief: dict[str, Any],
    fallback_reason: str | None,
    created_at: datetime,
) -> tuple[RecallSummaryRecord, list[RecallSourceItemRecord]]:
    """Build one recall summary row and one source row per considered candidate."""

    candidate_pack = recall_telemetry.get("candidate_pack", {})
    if not isinstance(candidate_pack, dict):
        candidate_pack = {}
    candidate_size = estimate_read_pack_size(pack=candidate_pack)
    source_payloads = recall_telemetry.get("source_items")
    if not isinstance(source_payloads, list):
        source_payloads = []

    source_items: list[RecallSourceItemRecord] = []
    for item in source_payloads:
        if not isinstance(item, dict):
            continue
        source_items.append(
            RecallSourceItemRecord(
                invocation_id=invocation_id,
                ordinal=int(item["ordinal"]),
                source_kind=str(item["source_kind"]),
                source_id=str(item["source_id"]),
                input_section=str(item["input_section"]),
                output_section=_optional_string(item.get("output_section")),
            )
        )

    brief_payload = {"brief": brief, "fallback_reason": fallback_reason}
    summary = RecallSummaryRecord(
        invocation_id=invocation_id,
        query_text=request.query,
        candidate_token_estimate=int(candidate_size["pack_token_estimate"]),
        brief_token_estimate=_estimate_tokens_from_text(_compact_json(brief_payload)),
        fallback_reason=fallback_reason,
        created_at=created_at,
    )
    return summary, source_items
