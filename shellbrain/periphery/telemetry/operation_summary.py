"""Helpers for assembling operation telemetry records from handler inputs and outputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from shellbrain.core.contracts.errors import ErrorCode
from shellbrain.core.contracts.requests import MemoryCreateRequest, MemoryReadRequest, MemoryUpdateRequest
from shellbrain.core.entities.telemetry import (
    OperationInvocationRecord,
    ReadResultItemRecord,
    ReadSummaryRecord,
    SessionSelectionSummary,
    WriteEffectItemRecord,
    WriteSummaryRecord,
)


def build_operation_invocation_record(
    *,
    invocation_id: str,
    command: str,
    repo_id: str,
    repo_root: str,
    no_sync: bool,
    selection_summary: SessionSelectionSummary,
    result: dict[str, Any],
    error_stage: str | None,
    total_latency_ms: int,
) -> OperationInvocationRecord:
    """Build the parent invocation row from one finished handler result."""

    first_error = _first_error(result)
    return OperationInvocationRecord(
        id=invocation_id,
        command=command,
        repo_id=repo_id,
        repo_root=repo_root,
        no_sync=no_sync,
        selected_host_app=selection_summary.selected_host_app,
        selected_host_session_key=selection_summary.selected_host_session_key,
        selected_thread_id=selection_summary.selected_thread_id,
        selected_episode_id=selection_summary.selected_episode_id,
        matching_candidate_count=selection_summary.matching_candidate_count,
        selection_ambiguous=selection_summary.selection_ambiguous,
        outcome=str(result.get("status") or "error"),
        error_stage=error_stage,
        error_code=first_error["code"],
        error_message=first_error["message"],
        total_latency_ms=total_latency_ms,
        poller_start_attempted=False,
        poller_started=False,
        created_at=datetime.now(timezone.utc),
    )


def build_read_summary_records(
    *,
    invocation_id: str,
    agent_payload: dict[str, Any],
    request: MemoryReadRequest,
    pack: dict[str, Any],
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

    summary = ReadSummaryRecord(
        invocation_id=invocation_id,
        query_text=request.query,
        mode=request.mode,
        requested_limit=agent_payload.get("limit") if isinstance(agent_payload.get("limit"), int) else None,
        effective_limit=int(request.limit or len(items) or 0),
        include_global=request.include_global,
        kinds_filter=list(request.kinds) if request.kinds is not None else None,
        direct_count=len(direct),
        explicit_related_count=len(explicit_related),
        implicit_related_count=len(implicit_related),
        total_returned=len(items),
        zero_results=len(items) == 0,
        created_at=datetime.now(timezone.utc),
    )
    return summary, items


def build_write_summary_records(
    *,
    invocation_id: str,
    command: str,
    request: MemoryCreateRequest | MemoryUpdateRequest,
    planned_side_effects: list[dict[str, Any]],
) -> tuple[WriteSummaryRecord, list[WriteEffectItemRecord]]:
    """Build one write summary row and one compact effect row per planned side effect."""

    created_memory_count = 0
    archived_memory_count = 0
    utility_observation_count = 0
    association_effect_count = 0
    fact_update_count = 0
    effect_items: list[WriteEffectItemRecord] = []

    for ordinal, effect in enumerate(planned_side_effects, start=1):
        effect_type = str(effect["effect_type"])
        params = effect["params"]
        assert isinstance(params, dict)
        if effect_type == "memory.create":
            created_memory_count += 1
        elif effect_type == "memory.archive_state" and bool(params.get("archived")):
            archived_memory_count += 1
        elif effect_type == "utility_observation.append":
            utility_observation_count += 1
        elif effect_type == "association.upsert_and_observe":
            association_effect_count += 1
        elif effect_type == "fact_update.create":
            fact_update_count += 1

        effect_items.append(
            WriteEffectItemRecord(
                invocation_id=invocation_id,
                ordinal=ordinal,
                effect_type=effect_type,
                repo_id=str(getattr(request, "repo_id")),
                primary_memory_id=_primary_memory_id(params),
                secondary_memory_id=_secondary_memory_id(params),
                params_json=_compact_effect_params(params),
            )
        )

    if isinstance(request, MemoryCreateRequest):
        evidence_ref_count = len(request.memory.evidence_refs)
        target_memory_id = _target_memory_id_from_create(planned_side_effects)
        target_kind = request.memory.kind
        update_type = None
        scope = request.memory.scope
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
        planned_effect_count=len(planned_side_effects),
        created_memory_count=created_memory_count,
        archived_memory_count=archived_memory_count,
        utility_observation_count=utility_observation_count,
        association_effect_count=association_effect_count,
        fact_update_count=fact_update_count,
        created_at=datetime.now(timezone.utc),
    )
    return summary, effect_items


def infer_error_stage_from_errors(errors: list[dict[str, Any]], *, default_stage: str) -> str:
    """Map structured error codes to telemetry stages when validation failed."""

    if not errors:
        return default_stage
    code = errors[0].get("code")
    normalized = code.value if isinstance(code, ErrorCode) else str(code)
    if normalized == ErrorCode.SCHEMA_ERROR.value and default_stage == "schema_validation":
        return "schema_validation"
    if normalized == ErrorCode.SCHEMA_ERROR.value and default_stage == "contract_validation":
        return "contract_validation"
    if normalized == ErrorCode.SEMANTIC_ERROR.value:
        return "semantic_validation"
    if normalized == ErrorCode.INTEGRITY_ERROR.value:
        return "integrity_validation"
    return default_stage


def _first_error(result: dict[str, Any]) -> dict[str, str | None]:
    """Return the first response error in a stable telemetry-friendly shape."""

    errors = result.get("errors")
    if not isinstance(errors, list) or not errors:
        return {"code": None, "message": None}
    first = errors[0]
    if not isinstance(first, dict):
        return {"code": None, "message": str(first)}
    code = first.get("code")
    normalized_code = code.value if isinstance(code, ErrorCode) else (str(code) if code is not None else None)
    message = first.get("message")
    return {
        "code": normalized_code,
        "message": str(message) if message is not None else None,
    }


def _target_memory_id_from_create(planned_side_effects: list[dict[str, Any]]) -> str:
    """Extract the created memory id from one create side-effect plan."""

    for effect in planned_side_effects:
        if str(effect.get("effect_type")) != "memory.create":
            continue
        params = effect.get("params")
        if isinstance(params, dict) and isinstance(params.get("memory_id"), str):
            return str(params["memory_id"])
    raise ValueError("Create telemetry expected one memory.create side effect.")


def _compact_effect_params(params: dict[str, Any]) -> dict[str, Any]:
    """Drop bulky fields so telemetry stores compact, queryable side-effect metadata."""

    return {
        str(key): value
        for key, value in params.items()
        if key not in {"text", "vector"}
    }


def _primary_memory_id(params: dict[str, Any]) -> str | None:
    """Extract the primary memory identifier from one side-effect payload when present."""

    for key in ("memory_id", "from_memory_id", "old_fact_id", "problem_id", "change_id"):
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


def _optional_string(value: object) -> str | None:
    """Return a string value or None when the field is absent."""

    return str(value) if isinstance(value, str) else None
