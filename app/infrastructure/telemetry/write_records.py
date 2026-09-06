"""Write telemetry record builders."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.use_cases.memories.add.request import MemoryAddRequest
from app.core.use_cases.memories.writes import MemoryWrite
from app.core.use_cases.memories.update.request import (
    MemoryBatchUpdateRequest,
    MemoryUpdateRequest,
)
from app.infrastructure.telemetry.records import (
    WriteEffectItemRecord,
    WriteSummaryRecord,
)

__all__ = ["build_write_summary_records"]


def build_write_summary_records(
    *,
    invocation_id: str,
    command: str,
    request: MemoryAddRequest | MemoryUpdateRequest | MemoryBatchUpdateRequest,
    completed_writes: list[MemoryWrite],
    created_at: datetime,
) -> tuple[WriteSummaryRecord, list[WriteEffectItemRecord]]:
    """Build one write summary row and one compact effect row per completed write."""

    effects = completed_writes
    created_memory_count = 0
    archived_memory_count = 0
    utility_observation_count = 0
    association_effect_count = 0
    fact_update_count = 0
    effect_items: list[WriteEffectItemRecord] = []

    for ordinal, effect in enumerate(effects, start=1):
        effect_type = effect.effect_type
        params = effect.params
        params_dict = params
        if effect_type == "memory.create":
            created_memory_count += 1
        elif (
            effect_type == "memory.lifecycle_update" and params["status"] == "archived"
        ):
            archived_memory_count += 1
        elif effect_type == "utility_observation.append":
            utility_observation_count += 1
        elif effect_type == "association.upsert_and_observe":
            association_effect_count += 1
        elif effect_type == "structural_fact_change.create":
            fact_update_count += 1

        effect_items.append(
            WriteEffectItemRecord(
                invocation_id=invocation_id,
                ordinal=ordinal,
                effect_type=effect_type,
                repo_id=str(getattr(request, "repo_id")),
                primary_memory_id=_primary_memory_id(params_dict),
                secondary_memory_id=_secondary_memory_id(params_dict),
                params_json=_compact_effect_params(params_dict),
            )
        )

    if isinstance(request, MemoryAddRequest):
        evidence_ref_count = len(request.memory.evidence_refs)
        target_memory_id = str(effects[0].params["memory_id"])
        target_kind = request.memory.kind
        update_type = None
        scope = request.memory.scope
    elif isinstance(request, MemoryBatchUpdateRequest):
        evidence_ref_count = sum(
            len(item.update.evidence_refs or []) for item in request.updates
        )
        target_memory_id = request.updates[0].update.problem_id
        target_kind = None
        update_type = "utility_vote_batch"
        scope = None
    else:
        evidence_ref_count = len(getattr(request.update, "evidence_refs", []) or [])
        target_memory_id = request.memory_id
        target_kind = None
        update_type = request.update.type
        scope = None

    summary = WriteSummaryRecord(
        invocation_id=invocation_id,
        operation_command=command,
        target_memory_id=target_memory_id,
        target_kind=target_kind,
        update_type=update_type,
        scope=scope,
        evidence_ref_count=evidence_ref_count,
        planned_effect_count=len(effects),
        created_memory_count=created_memory_count,
        archived_memory_count=archived_memory_count,
        utility_observation_count=utility_observation_count,
        association_effect_count=association_effect_count,
        fact_update_count=fact_update_count,
        created_at=created_at,
    )
    return summary, effect_items


def _compact_effect_params(params: dict[str, Any]) -> dict[str, Any]:
    """Drop bulky fields so telemetry stores compact, queryable side-effect metadata."""

    return {
        str(key): _jsonable(value)
        for key, value in params.items()
        if key not in {"text", "vector"}
    }


def _jsonable(value: Any) -> Any:
    """Return one value in a JSON-safe shape for write telemetry."""

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _primary_memory_id(params: dict[str, Any]) -> str | None:
    """Extract the primary memory identifier from one side-effect payload when present."""

    for key in (
        "memory_id",
        "from_memory_id",
        "old_fact_id",
        "problem_id",
        "change_id",
    ):
        value = params.get(key)
        if isinstance(value, str):
            return value
    return None


def _secondary_memory_id(params: dict[str, Any]) -> str | None:
    """Extract the secondary memory identifier from one side-effect payload when present."""

    for key in ("to_memory_id", "new_fact_id", "attempt_id"):
        value = params.get(key)
        if isinstance(value, str):
            return value
    return None
