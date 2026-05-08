"""Shellbrain-managed Cursor CLI statusline and token sidecar capture."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys


def main() -> int:
    """Read one Cursor statusline payload, append a usage sidecar row, and print status text."""

    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0

    session_id = _clean_string(payload.get("session_id"))
    if session_id is None:
        return 0

    state = _load_session_state(session_id=session_id)
    record = _build_usage_record(payload=payload, state=state)
    if record is not None and record["usage_key"] != state.get("last_usage_key"):
        _append_usage_record(session_id=session_id, record=record)
        _write_session_state(session_id=session_id, record=record)

    print(_render_statusline(payload), end="")
    return 0


def _build_usage_record(*, payload: dict[str, object], state: dict[str, object]) -> dict[str, object] | None:
    """Build one append-only usage row from a Cursor statusline payload."""

    context_window = payload.get("context_window")
    if not isinstance(context_window, dict):
        context_window = {}
    current_usage = context_window.get("current_usage")
    if not isinstance(current_usage, dict):
        current_usage = {}

    raw_input_tokens = _coerce_non_negative_int(current_usage.get("input_tokens", current_usage.get("inputTokens")))
    raw_output_tokens = _coerce_non_negative_int(current_usage.get("output_tokens", current_usage.get("outputTokens")))
    raw_reasoning_output_tokens = _coerce_non_negative_int(
        current_usage.get("reasoning_output_tokens", current_usage.get("reasoningOutputTokens"))
    )
    raw_cached_input_tokens_total = _coerce_non_negative_int(
        current_usage.get("cached_input_tokens", current_usage.get("cachedInputTokens"))
    )
    raw_cache_read_input_tokens = _coerce_non_negative_int(
        current_usage.get("cache_read_input_tokens", current_usage.get("cacheReadInputTokens"))
    )
    raw_cache_creation_input_tokens = _coerce_non_negative_int(
        current_usage.get("cache_creation_input_tokens", current_usage.get("cacheCreationInputTokens"))
    )

    total_input_tokens = _coerce_non_negative_int(context_window.get("total_input_tokens"))
    total_output_tokens = _coerce_non_negative_int(context_window.get("total_output_tokens"))
    previous_total_input_tokens = _coerce_non_negative_int(state.get("total_input_tokens"))
    previous_total_output_tokens = _coerce_non_negative_int(state.get("total_output_tokens"))

    input_tokens = raw_input_tokens
    output_tokens = raw_output_tokens
    reasoning_output_tokens = raw_reasoning_output_tokens
    cached_input_tokens_total = raw_cached_input_tokens_total
    cache_read_input_tokens = raw_cache_read_input_tokens
    cache_creation_input_tokens = raw_cache_creation_input_tokens
    if (
        input_tokens == 0
        and output_tokens == 0
        and reasoning_output_tokens == 0
        and cached_input_tokens_total == 0
    ):
        input_tokens = max(total_input_tokens - previous_total_input_tokens, 0)
        output_tokens = max(total_output_tokens - previous_total_output_tokens, 0)
    if input_tokens == 0 and output_tokens == 0 and reasoning_output_tokens == 0 and cached_input_tokens_total == 0:
        return None

    occurred_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    model = payload.get("model")
    model_id = None
    if isinstance(model, dict):
        model_id = _clean_string(model.get("id"))
    usage_key = "|".join(
        [
            model_id or "",
            str(input_tokens),
            str(output_tokens),
            str(reasoning_output_tokens),
            str(cached_input_tokens_total),
            str(total_input_tokens),
            str(total_output_tokens),
        ]
    )
    return {
        "session_id": _clean_string(payload.get("session_id")),
        "usage_key": usage_key,
        "occurred_at": occurred_at,
        "provider": _provider_from_model_id(model_id),
        "model_id": model_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "cached_input_tokens_total": cached_input_tokens_total,
        "cache_read_input_tokens": cache_read_input_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "capture_quality": "estimated",
        "raw_payload": {
            "context_window": context_window,
            "model": model if isinstance(model, dict) else {},
        },
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
    }


def _append_usage_record(*, session_id: str, record: dict[str, object]) -> None:
    """Append one JSONL usage row for a Cursor session."""

    sidecar_path = _sidecar_path(session_id=session_id)
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    with sidecar_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _load_session_state(*, session_id: str) -> dict[str, object]:
    """Load the last persisted Cursor statusline state for one session."""

    state_path = _state_path(session_id=session_id)
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_session_state(*, session_id: str, record: dict[str, object]) -> None:
    """Persist the latest Cursor statusline state for one session."""

    state_path = _state_path(session_id=session_id)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "last_usage_key": record.get("usage_key"),
                "total_input_tokens": record.get("total_input_tokens"),
                "total_output_tokens": record.get("total_output_tokens"),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _render_statusline(payload: dict[str, object]) -> str:
    """Render a small neutral Cursor statusline."""

    model = payload.get("model")
    display_name = None
    if isinstance(model, dict):
        display_name = _clean_string(model.get("display_name")) or _clean_string(model.get("id"))
    context_window = payload.get("context_window")
    used_percentage = None
    if isinstance(context_window, dict):
        used_percentage = context_window.get("used_percentage")
    if isinstance(used_percentage, (int, float)):
        return f"[{display_name or 'Cursor'}] ctx {int(used_percentage)}%"
    return f"[{display_name or 'Cursor'}]"


def _sidecar_path(*, session_id: str) -> Path:
    """Return the JSONL sidecar path for one Cursor session."""

    return _cursor_home() / "shellbrain" / "model-usage" / f"{session_id}.jsonl"


def _state_path(*, session_id: str) -> Path:
    """Return the state file used to dedupe Cursor statusline writes."""

    return _cursor_home() / "shellbrain" / "model-usage-state" / f"{session_id}.json"


def _cursor_home() -> Path:
    """Return the active Cursor home path."""

    raw = os.getenv("CURSOR_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".cursor").resolve()


def _provider_from_model_id(model_id: str | None) -> str | None:
    """Infer one provider label from a Cursor model identifier."""

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


def _coerce_non_negative_int(value: object) -> int:
    """Return a non-negative integer from a loosely-typed token count."""

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


def _clean_string(value: object) -> str | None:
    """Return one stripped string when present."""

    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


if __name__ == "__main__":
    raise SystemExit(main())
