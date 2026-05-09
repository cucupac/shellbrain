"""Normalize host token usage into append-only model-usage records."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.infrastructure.host_apps.transcripts.claude_code import (
    extract_claude_code_model_usage,
)
from app.infrastructure.host_apps.transcripts.codex import extract_codex_model_usage
from app.infrastructure.host_apps.transcripts.cursor import extract_cursor_model_usage
from app.infrastructure.telemetry.records import ModelUsageRecord


def collect_model_usage_records_for_session(
    *,
    repo_id: str,
    host_app: str,
    host_session_key: str,
    thread_id: str | None,
    episode_id: str | None,
    transcript_path: Path,
) -> list[ModelUsageRecord]:
    """Extract and materialize normalized model-usage rows for one host session."""

    extracted_rows = extract_host_model_usage(
        host_app=host_app,
        host_session_key=host_session_key,
        transcript_path=transcript_path,
    )
    return build_model_usage_records(
        repo_id=repo_id,
        host_app=host_app,
        host_session_key=host_session_key,
        thread_id=thread_id,
        episode_id=episode_id,
        extracted_rows=extracted_rows,
    )


def extract_host_model_usage(
    *,
    host_app: str,
    host_session_key: str,
    transcript_path: Path,
) -> list[dict[str, Any]]:
    """Return normalized host usage rows before DB-specific record materialization."""

    transcript_path = Path(transcript_path)
    if host_app == "codex":
        return extract_codex_model_usage(
            host_session_key=host_session_key,
            transcript_path=transcript_path,
        )
    if host_app == "claude_code":
        return extract_claude_code_model_usage(
            host_session_key=host_session_key,
            transcript_path=transcript_path,
        )
    if host_app == "cursor":
        rows = extract_cursor_model_usage(
            host_session_key=host_session_key,
            transcript_path=transcript_path,
        )
        rows.extend(
            _extract_cursor_statusline_sidecar_usage(host_session_key=host_session_key)
        )
        return rows
    raise ValueError(f"Unsupported host app for model-usage extraction: {host_app}")


def build_model_usage_records(
    *,
    repo_id: str,
    host_app: str,
    host_session_key: str,
    thread_id: str | None,
    episode_id: str | None,
    extracted_rows: list[dict[str, Any]],
) -> list[ModelUsageRecord]:
    """Convert normalized host usage rows into typed DB records."""

    records: list[ModelUsageRecord] = []
    for row in extracted_rows:
        model_id = _clean_string(row.get("model_id"))
        provider = _clean_string(row.get("provider")) or _infer_provider(
            model_id=model_id
        )
        raw_usage_json = row.get("raw_usage_json")
        if not isinstance(raw_usage_json, dict):
            raw_usage_json = {}
        records.append(
            ModelUsageRecord(
                id=str(uuid4()),
                repo_id=repo_id,
                thread_id=thread_id,
                episode_id=episode_id,
                host_app=host_app,
                host_session_key=host_session_key,
                host_usage_key=str(row["host_usage_key"]),
                source_kind=str(row.get("source_kind") or "unknown"),
                occurred_at=_parse_occurred_at(row.get("occurred_at")),
                agent_role=_clean_string(row.get("agent_role")) or "foreground",
                provider=provider,
                model_id=model_id,
                input_tokens=_coerce_non_negative_int(row.get("input_tokens")),
                output_tokens=_coerce_non_negative_int(row.get("output_tokens")),
                reasoning_output_tokens=_coerce_non_negative_int(
                    row.get("reasoning_output_tokens")
                ),
                cached_input_tokens_total=_coerce_non_negative_int(
                    row.get("cached_input_tokens_total")
                ),
                cache_read_input_tokens=_coerce_non_negative_int(
                    row.get("cache_read_input_tokens")
                ),
                cache_creation_input_tokens=_coerce_non_negative_int(
                    row.get("cache_creation_input_tokens")
                ),
                capture_quality=_clean_string(row.get("capture_quality")) or "exact",
                raw_usage_json=raw_usage_json,
                created_at=None,
            )
        )
    return records


def _extract_cursor_statusline_sidecar_usage(
    *, host_session_key: str
) -> list[dict[str, Any]]:
    """Read Shellbrain-managed Cursor statusline sidecar rows when present."""

    sidecar_path = _cursor_statusline_sidecar_path(host_session_key=host_session_key)
    if not sidecar_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with sidecar_path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            raw_line = raw_line.rstrip("\n")
            if not raw_line:
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if str(payload.get("session_id") or "") != host_session_key:
                continue
            rows.append(
                {
                    "host_usage_key": str(
                        payload.get("usage_key")
                        or _fallback_usage_key(
                            prefix="cursor-sidecar",
                            raw_line=raw_line,
                            line_number=line_number,
                        )
                    ),
                    "source_kind": "cursor_statusline_sidecar",
                    "occurred_at": str(payload.get("occurred_at") or ""),
                    "agent_role": "foreground",
                    "provider": _clean_string(payload.get("provider")),
                    "model_id": _clean_string(payload.get("model_id")),
                    "input_tokens": payload.get("input_tokens"),
                    "output_tokens": payload.get("output_tokens"),
                    "reasoning_output_tokens": payload.get("reasoning_output_tokens"),
                    "cached_input_tokens_total": payload.get(
                        "cached_input_tokens_total"
                    ),
                    "cache_read_input_tokens": payload.get("cache_read_input_tokens"),
                    "cache_creation_input_tokens": payload.get(
                        "cache_creation_input_tokens"
                    ),
                    "capture_quality": _clean_string(payload.get("capture_quality"))
                    or "estimated",
                    "raw_usage_json": payload.get("raw_payload")
                    if isinstance(payload.get("raw_payload"), dict)
                    else payload,
                }
            )
    return rows


def _cursor_statusline_sidecar_path(*, host_session_key: str) -> Path:
    """Return the Shellbrain-managed Cursor statusline sidecar path for one session."""

    cursor_home = (
        Path(os.getenv("CURSOR_HOME") or (Path.home() / ".cursor"))
        .expanduser()
        .resolve()
    )
    return cursor_home / "shellbrain" / "model-usage" / f"{host_session_key}.jsonl"


def _infer_provider(*, model_id: str | None) -> str | None:
    """Infer one provider label from a host-exposed model identifier when obvious."""

    if model_id is None:
        return None
    lowered = model_id.lower()
    if lowered.startswith("claude"):
        return "anthropic"
    if lowered.startswith(("gpt", "o1", "o3", "o4", "codex")) or "openai" in lowered:
        return "openai"
    if lowered.startswith("gemini"):
        return "google"
    return None


def _parse_occurred_at(value: Any) -> datetime:
    """Parse one host usage timestamp into a timezone-aware datetime."""

    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _coerce_non_negative_int(value: Any) -> int:
    """Return a non-negative integer token count, defaulting invalid values to zero."""

    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(value, 0)
    if isinstance(value, float):
        return max(int(value), 0)
    if isinstance(value, str) and value.strip():
        try:
            return max(int(value), 0)
        except ValueError:
            return 0
    return 0


def _clean_string(value: Any) -> str | None:
    """Return one trimmed string when present."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _fallback_usage_key(*, prefix: str, raw_line: str, line_number: int) -> str:
    """Build one stable usage key when a source does not expose one directly."""

    digest = hashlib.sha1(raw_line.encode("utf-8"), usedforsecurity=False).hexdigest()[
        :16
    ]
    return f"{prefix}-{line_number}-{digest}"
