"""Helpers for assembling operation telemetry records from handler inputs and outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.errors import ErrorCode
from app.core.entities.runtime_context import RuntimeContext, SessionSelectionSummary
from app.infrastructure.telemetry.records import OperationInvocationRecord


def build_operation_invocation_record(
    *,
    command: str,
    repo_id: str,
    runtime_context: RuntimeContext,
    selection_summary: SessionSelectionSummary,
    result: dict[str, Any],
    error_stage: str | None,
    total_latency_ms: int,
    created_at: datetime,
) -> OperationInvocationRecord:
    """Build the parent invocation row from one finished handler result."""

    first_error = _first_error(result)
    caller_identity = runtime_context.caller_identity
    guidance_codes = _guidance_codes(result)
    return OperationInvocationRecord(
        id=runtime_context.invocation_id,
        command=command,
        repo_id=repo_id,
        repo_root=runtime_context.repo_root,
        no_sync=runtime_context.no_sync,
        caller_id=caller_identity.canonical_id if caller_identity is not None else None,
        caller_trust_level=caller_identity.trust_level.value
        if caller_identity is not None
        else None,
        identity_failure_code=runtime_context.caller_identity_error.code.value
        if runtime_context.caller_identity_error is not None
        else None,
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
        guidance_codes=guidance_codes,
        created_at=created_at,
    )


def infer_error_stage_from_errors(
    errors: list[dict[str, Any]], *, default_stage: str
) -> str:
    """Map structured error codes to telemetry stages when validation failed."""

    if not errors:
        return default_stage
    code = errors[0].get("code")
    normalized = code.value if isinstance(code, ErrorCode) else str(code)
    if (
        normalized == ErrorCode.SCHEMA_ERROR.value
        and default_stage == "schema_validation"
    ):
        return "schema_validation"
    if (
        normalized == ErrorCode.SCHEMA_ERROR.value
        and default_stage == "contract_validation"
    ):
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
    normalized_code = (
        code.value
        if isinstance(code, ErrorCode)
        else (str(code) if code is not None else None)
    )
    message = first.get("message")
    return {
        "code": normalized_code,
        "message": str(message) if message is not None else None,
    }


def _guidance_codes(result: dict[str, Any]) -> list[str]:
    """Return stable guidance codes from one successful result."""

    data = result.get("data")
    if not isinstance(data, dict):
        return []
    guidance = data.get("guidance")
    if not isinstance(guidance, list):
        return []
    codes: list[str] = []
    for item in guidance:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        if isinstance(code, str):
            codes.append(code)
    return codes
