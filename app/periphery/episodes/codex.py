"""Codex-host transcript discovery and normalization helpers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from app.periphery.episodes.tool_filter import should_keep_tool_result, summarize_tool_result


def resolve_codex_transcript_path(
    *,
    host_session_key: str,
    search_roots: Sequence[Path],
    last_known_path: Path | None = None,
) -> Path:
    """Resolve one Codex rollout transcript path from a thread id."""

    if last_known_path is not None and last_known_path.exists():
        return last_known_path
    candidates: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        candidates.extend(sorted(root.rglob(f"*{host_session_key}*.jsonl")))
    if not candidates:
        raise FileNotFoundError(
            f"Codex transcript source for session '{host_session_key}' could not be found."
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def find_latest_codex_session_for_repo(*, repo_root: Path, search_roots: Sequence[Path]) -> dict[str, Any] | None:
    """Return the most recently updated Codex session for one repo root."""

    candidates = list_codex_sessions_for_repo(repo_root=repo_root, search_roots=search_roots)
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate["updated_at"])


def list_codex_sessions_for_repo(*, repo_root: Path, search_roots: Sequence[Path]) -> list[dict[str, Any]]:
    """Return all repo-matching Codex sessions under the bounded search roots."""

    candidates: list[dict[str, Any]] = []
    resolved_repo_root = repo_root.resolve()
    for root in search_roots:
        if not root.exists():
            continue
        for transcript_path in root.rglob("*.jsonl"):
            metadata = _read_session_meta(transcript_path)
            cwd = metadata.get("cwd")
            session_id = metadata.get("id")
            if not isinstance(cwd, str) or not isinstance(session_id, str):
                continue
            try:
                if Path(cwd).resolve() != resolved_repo_root:
                    continue
            except FileNotFoundError:
                continue
            candidates.append(
                {
                    "host_app": "codex",
                    "host_session_key": session_id,
                    "transcript_path": transcript_path,
                    "updated_at": transcript_path.stat().st_mtime,
                }
            )
    return candidates


def normalize_codex_transcript(*, host_session_key: str, transcript_path: Path) -> list[dict[str, Any]]:
    """Normalize one Codex transcript into shared compact event dictionaries."""

    events: list[dict[str, Any]] = []
    function_calls: dict[str, dict[str, Any]] = {}
    with transcript_path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            raw_line = raw_line.rstrip("\n")
            if not raw_line:
                continue
            payload = json.loads(raw_line)
            line_type = payload.get("type")

            if line_type == "message":
                event = _normalize_simple_message(payload, host_session_key=host_session_key)
                if event is not None:
                    events.append(event)
                continue

            if line_type == "tool_result":
                event = _normalize_simple_tool_result(payload, host_session_key=host_session_key)
                if event is not None:
                    events.append(event)
                continue

            if line_type == "event_msg":
                event = _normalize_event_msg(
                    payload,
                    host_session_key=host_session_key,
                    raw_line=raw_line,
                    line_number=line_number,
                )
                if event is not None:
                    events.append(event)
                continue

            if line_type != "response_item":
                continue

            item = payload.get("payload", {})
            item_type = item.get("type")
            if item_type == "message":
                event = _normalize_response_message(
                    payload,
                    host_session_key=host_session_key,
                    raw_line=raw_line,
                    line_number=line_number,
                )
                if event is not None:
                    events.append(event)
                continue
            if item_type == "function_call":
                call_id = item.get("call_id")
                if isinstance(call_id, str):
                    function_calls[call_id] = item
                continue
            if item_type == "function_call_output":
                event = _normalize_function_call_output(
                    payload,
                    host_session_key=host_session_key,
                    raw_line=raw_line,
                    line_number=line_number,
                    function_calls=function_calls,
                )
                if event is not None:
                    events.append(event)
                continue

    return events


def extract_codex_model_usage(*, host_session_key: str, transcript_path: Path) -> list[dict[str, Any]]:
    """Extract per-call token usage from one Codex transcript."""

    rows: list[dict[str, Any]] = []
    with transcript_path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            raw_line = raw_line.rstrip("\n")
            if not raw_line:
                continue
            payload = json.loads(raw_line)
            if payload.get("type") != "event_msg":
                continue
            item = payload.get("payload", {})
            if item.get("type") != "token_count":
                continue
            info = item.get("info")
            if not isinstance(info, dict):
                continue
            usage = info.get("last_token_usage")
            if not isinstance(usage, dict):
                continue
            rows.append(
                {
                    "host_usage_key": _usage_key(raw_line=raw_line, line_number=line_number, prefix="codex-token-count"),
                    "source_kind": "codex_transcript",
                    "occurred_at": str(payload.get("timestamp") or ""),
                    "agent_role": "foreground",
                    "provider": "openai",
                    "model_id": None,
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                    "reasoning_output_tokens": usage.get("reasoning_output_tokens"),
                    "cached_input_tokens_total": usage.get("cached_input_tokens"),
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "capture_quality": "exact",
                    "raw_usage_json": {
                        "last_token_usage": usage,
                        "model_context_window": info.get("model_context_window"),
                    },
                }
            )
    return rows


def _normalize_simple_message(payload: dict[str, Any], *, host_session_key: str) -> dict[str, Any] | None:
    """Normalize the synthetic message shape used by tests."""

    role = payload.get("role")
    text = payload.get("text")
    if role not in {"user", "assistant"} or not isinstance(text, str) or not text.strip():
        return None
    return _build_event(
        host_session_key=host_session_key,
        host_event_key=str(payload.get("event_id") or _hash_event(payload)),
        source=str(role),
        occurred_at=str(payload.get("timestamp") or ""),
        content_kind="message",
        content_text=text.strip(),
    )


def _normalize_simple_tool_result(payload: dict[str, Any], *, host_session_key: str) -> dict[str, Any] | None:
    """Normalize the synthetic tool-result shape used by tests."""

    summary = payload.get("summary") if isinstance(payload.get("summary"), str) else None
    text = payload.get("text") if isinstance(payload.get("text"), str) else None
    tool_name = payload.get("tool_name") if isinstance(payload.get("tool_name"), str) else None
    status = payload.get("status") if isinstance(payload.get("status"), str) else None
    if not should_keep_tool_result(
        tool_name=tool_name,
        status=status,
        text=text,
        summary=summary,
    ):
        return None
    return _build_event(
        host_session_key=host_session_key,
        host_event_key=str(payload.get("event_id") or _hash_event(payload)),
        source="tool",
        occurred_at=str(payload.get("timestamp") or ""),
        content_kind="tool_result",
        content_text=summarize_tool_result(
            tool_name=tool_name,
            status=status,
            text=text,
            summary=summary,
        ),
        extra_fields={
            "tool_name": _normalized_tool_name(tool_name=tool_name, command=None),
            "status": _normalized_tool_status(status=status, text=text, summary=summary),
            "is_error": _normalized_tool_status(status=status, text=text, summary=summary) == "error",
        },
    )


def _normalize_event_msg(
    payload: dict[str, Any],
    *,
    host_session_key: str,
    raw_line: str,
    line_number: int,
) -> dict[str, Any] | None:
    """Normalize user-visible Codex event message records."""

    item = payload.get("payload", {})
    item_type = item.get("type")
    if item_type == "user_message":
        text = item.get("message")
        if isinstance(text, str) and text.strip():
            return _build_event(
                host_session_key=host_session_key,
                host_event_key=_fallback_key(payload, raw_line, line_number),
                source="user",
                occurred_at=str(payload.get("timestamp") or ""),
                content_kind="message",
                content_text=text.strip(),
            )
    if item_type == "agent_message":
        text = item.get("message")
        if isinstance(text, str) and text.strip():
            return _build_event(
                host_session_key=host_session_key,
                host_event_key=_fallback_key(payload, raw_line, line_number),
                source="assistant",
                occurred_at=str(payload.get("timestamp") or ""),
                content_kind="message",
                content_text=text.strip(),
            )
    return None


def _normalize_response_message(
    payload: dict[str, Any],
    *,
    host_session_key: str,
    raw_line: str,
    line_number: int,
) -> dict[str, Any] | None:
    """Normalize canonical assistant response items from Codex."""

    item = payload.get("payload", {})
    role = item.get("role")
    if role != "assistant":
        return None
    text = _extract_codex_message_text(item.get("content"))
    if not text:
        return None
    return _build_event(
        host_session_key=host_session_key,
        host_event_key=_fallback_key(payload, raw_line, line_number),
        source="assistant",
        occurred_at=str(payload.get("timestamp") or ""),
        content_kind="message",
        content_text=text,
    )


def _normalize_function_call_output(
    payload: dict[str, Any],
    *,
    host_session_key: str,
    raw_line: str,
    line_number: int,
    function_calls: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Normalize one Codex tool result when it carries durable value."""

    item = payload.get("payload", {})
    call_id = item.get("call_id")
    call = function_calls.get(str(call_id)) if isinstance(call_id, str) else None
    tool_name = call.get("name") if isinstance(call, dict) else None
    command = _extract_codex_command(call)
    text = item.get("output") if isinstance(item.get("output"), str) else None
    if not should_keep_tool_result(
        tool_name=tool_name if isinstance(tool_name, str) else None,
        status=None,
        text=text,
        command=command,
    ):
        return None
    return _build_event(
        host_session_key=host_session_key,
        host_event_key=str(call_id or _fallback_key(payload, raw_line, line_number)),
        source="tool",
        occurred_at=str(payload.get("timestamp") or ""),
        content_kind="tool_result",
        content_text=summarize_tool_result(
            tool_name=tool_name if isinstance(tool_name, str) else None,
            status=None,
            text=text,
            command=command,
        ),
        extra_fields={
            "tool_name": _normalized_tool_name(
                tool_name=tool_name if isinstance(tool_name, str) else None,
                command=command,
            ),
            "status": _normalized_tool_status(status=None, text=text, summary=None),
            "is_error": _normalized_tool_status(status=None, text=text, summary=None) == "error",
        },
    )


def _extract_codex_message_text(content: Any) -> str:
    """Extract visible text from a Codex response-item content list."""

    if not isinstance(content, Iterable) or isinstance(content, (str, bytes)):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type not in {"input_text", "output_text", "text"}:
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts).strip()


def _extract_codex_command(call: dict[str, Any] | None) -> str | None:
    """Extract one shell command from a Codex function call when present."""

    if not isinstance(call, dict):
        return None
    arguments = call.get("arguments")
    if not isinstance(arguments, str):
        return None
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError:
        return None
    command = parsed.get("cmd")
    return command if isinstance(command, str) else None


def _read_session_meta(transcript_path: Path) -> dict[str, Any]:
    """Read the leading session_meta payload from one Codex rollout file when present."""

    try:
        with transcript_path.open(encoding="utf-8") as handle:
            first_line = handle.readline()
    except FileNotFoundError:
        return {}
    if not first_line:
        return {}
    payload = json.loads(first_line)
    if payload.get("type") != "session_meta":
        return {}
    metadata = payload.get("payload", {})
    return metadata if isinstance(metadata, dict) else {}


def _build_event(
    *,
    host_session_key: str,
    host_event_key: str,
    source: str,
    occurred_at: str,
    content_kind: str,
    content_text: str,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct one shared normalized event payload."""

    event = {
        "host_app": "codex",
        "host_session_key": host_session_key,
        "host_event_key": host_event_key,
        "source": source,
        "occurred_at": occurred_at,
        "content_kind": content_kind,
        "content_text": content_text,
        "raw_ref": f"codex://threads/{host_session_key}#event={host_event_key}",
    }
    if extra_fields:
        event.update(extra_fields)
    return event


def _normalized_tool_name(*, tool_name: str | None, command: str | None) -> str:
    """Normalize Codex tool identifiers into stable analytics-friendly names."""

    if isinstance(tool_name, str) and tool_name.strip():
        return tool_name.strip()
    if command:
        return "exec_command"
    return "unknown_tool"


def _normalized_tool_status(*, status: str | None, text: str | None, summary: str | None) -> str:
    """Derive one compact ok/error status for a normalized tool event."""

    if isinstance(status, str) and status.strip():
        normalized = status.strip().lower()
        return "error" if normalized in {"error", "failed", "failure"} else "ok"
    combined = " ".join(part for part in (summary, text) if isinstance(part, str)).lower()
    if any(token in combined for token in ("failed", "error", "exception")):
        return "error"
    match = re.search(r"process exited with code (\d+)", text or "", re.IGNORECASE)
    if match is not None and int(match.group(1)) != 0:
        return "error"
    return "ok"


def _fallback_key(payload: dict[str, Any], raw_line: str, line_number: int) -> str:
    """Build a stable upstream event key when the host does not expose one directly."""

    explicit = payload.get("event_id")
    if isinstance(explicit, str) and explicit:
        return explicit
    digest = hashlib.sha1(raw_line.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    return f"codex-line-{line_number}-{digest}"


def _hash_event(payload: dict[str, Any]) -> str:
    """Hash a small synthetic event deterministically."""

    encoded = json.dumps(payload, sort_keys=True)
    return hashlib.sha1(encoded.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


def _usage_key(*, raw_line: str, line_number: int, prefix: str) -> str:
    """Build one stable usage key for a transcript line."""

    digest = hashlib.sha1(raw_line.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    return f"{prefix}-{line_number}-{digest}"
