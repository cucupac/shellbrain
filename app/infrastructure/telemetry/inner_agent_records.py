"""Inner-agent telemetry record builders."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.infrastructure.telemetry.records import InnerAgentInvocationRecord

__all__ = ["build_inner_agent_invocation_records"]


def build_inner_agent_invocation_records(
    *,
    invocation_id: str,
    recall_telemetry: dict[str, Any],
    created_at: datetime,
) -> tuple[InnerAgentInvocationRecord, ...]:
    """Build inner-agent invocation rows from recall telemetry payloads."""

    payload = recall_telemetry.get("inner_agent")
    if not isinstance(payload, dict):
        return ()
    agent_name = str(payload.get("agent_name") or "build_context")
    return (
        InnerAgentInvocationRecord(
            id=f"{invocation_id}:{agent_name}:1",
            operation_invocation_id=invocation_id,
            agent_name=agent_name,
            provider=_optional_string(payload.get("provider")),
            model=_optional_string(payload.get("model")),
            reasoning=_optional_string(payload.get("reasoning")),
            status=str(payload.get("status") or "error"),
            fallback_used=bool(payload.get("fallback_used")),
            timeout_seconds=_optional_int(payload.get("timeout_seconds")),
            duration_ms=_optional_int(payload.get("duration_ms")) or 0,
            input_tokens=_optional_int(payload.get("input_tokens")),
            output_tokens=_optional_int(payload.get("output_tokens")),
            reasoning_output_tokens=_optional_int(
                payload.get("reasoning_output_tokens")
            ),
            cached_input_tokens_total=_optional_int(
                payload.get("cached_input_tokens_total")
            ),
            cache_read_input_tokens=_optional_int(payload.get("cache_read_input_tokens")),
            cache_creation_input_tokens=_optional_int(
                payload.get("cache_creation_input_tokens")
            ),
            capture_quality=_optional_string(payload.get("capture_quality")),
            private_read_count=_optional_int(payload.get("private_read_count")) or 0,
            concept_expansion_count=_optional_int(payload.get("concept_expansion_count"))
            or 0,
            error_code=_optional_string(payload.get("error_code")),
            error_message=_optional_string(payload.get("error_message")),
            created_at=created_at,
        ),
    )


def _optional_string(value: Any) -> str | None:
    """Return a non-empty string or None."""

    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(value: Any) -> int | None:
    """Return a non-negative integer or None."""

    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None
