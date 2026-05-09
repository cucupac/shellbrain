"""Cursor foreground-chat discovery and normalization helpers."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any
from urllib.parse import unquote, urlparse

from app.infrastructure.host_apps.transcripts.tool_filter import (
    should_keep_tool_result,
    summarize_tool_result,
)


_CURSOR_GLOBAL_DB = Path("globalStorage") / "state.vscdb"
_CURSOR_WORKSPACE_GLOB = Path("workspaceStorage")
_CURSOR_WORKSPACE_META = "workspace.json"
_ROLE_BY_TYPE = {
    1: "user",
    2: "assistant",
}


def default_cursor_user_roots() -> list[Path]:
    """Return the bounded default Cursor user roots for the current platform."""

    home = Path.home()
    appdata = os.getenv("APPDATA")
    if os.name == "nt" and appdata:
        return [Path(appdata).expanduser().resolve() / "Cursor" / "User"]
    if sys_platform_linux():
        return [(home / ".config" / "Cursor" / "User").resolve()]
    return [(home / "Library" / "Application Support" / "Cursor" / "User").resolve()]


def resolve_cursor_transcript_path(
    *,
    host_session_key: str,
    search_roots: Sequence[Path],
    last_known_path: Path | None = None,
) -> Path:
    """Resolve Cursor's global state database for one composer id."""

    if (
        last_known_path is not None
        and last_known_path.exists()
        and _cursor_db_has_composer(last_known_path, host_session_key)
    ):
        return last_known_path
    for root in _cursor_user_roots(search_roots):
        global_db = root / _CURSOR_GLOBAL_DB
        if _cursor_db_has_composer(global_db, host_session_key):
            return global_db
    raise FileNotFoundError(
        f"Cursor transcript source for session '{host_session_key}' could not be found."
    )


def find_latest_cursor_session_for_repo(
    *, repo_root: Path, search_roots: Sequence[Path]
) -> dict[str, Any] | None:
    """Return the most recently updated Cursor composer for one repo root."""

    candidates = list_cursor_sessions_for_repo(
        repo_root=repo_root, search_roots=search_roots
    )
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate["updated_at"])


def list_cursor_sessions_for_repo(
    *, repo_root: Path, search_roots: Sequence[Path]
) -> list[dict[str, Any]]:
    """Return all repo-matching active Cursor composers under the bounded search roots."""

    resolved_repo_root = repo_root.resolve()
    deduped: dict[tuple[Path, str], dict[str, Any]] = {}
    for user_root in _cursor_user_roots(search_roots):
        global_db = user_root / _CURSOR_GLOBAL_DB
        if not global_db.exists():
            continue
        for workspace_db in user_root.glob(
            str(_CURSOR_WORKSPACE_GLOB / "*" / "state.vscdb")
        ):
            workspace_root = workspace_db.parent
            workspace_path = _resolve_workspace_path(
                workspace_root / _CURSOR_WORKSPACE_META
            )
            if workspace_path is None:
                continue
            try:
                if workspace_path.resolve() != resolved_repo_root:
                    continue
            except FileNotFoundError:
                continue
            for composer_id in _active_workspace_composer_ids(workspace_db):
                composer = _read_cursor_json(global_db, f"composerData:{composer_id}")
                if not isinstance(composer, dict):
                    continue
                candidate = {
                    "host_app": "cursor",
                    "host_session_key": composer_id,
                    "transcript_path": global_db,
                    "updated_at": _composer_updated_at(
                        composer, fallback_path=global_db
                    ),
                }
                deduped[(global_db, composer_id)] = candidate
    return list(deduped.values())


def normalize_cursor_transcript(
    *, host_session_key: str, transcript_path: Path
) -> list[dict[str, Any]]:
    """Normalize one Cursor composer thread into shared compact event dictionaries."""

    composer = _read_cursor_json(transcript_path, f"composerData:{host_session_key}")
    if not isinstance(composer, dict):
        raise FileNotFoundError(
            f"Cursor transcript source for session '{host_session_key}' could not be found."
        )

    generating_ids = {
        bubble_id
        for bubble_id in composer.get("generatingBubbleIds", [])
        if isinstance(bubble_id, str) and bubble_id
    }
    events: list[dict[str, Any]] = []
    for index, header in enumerate(composer.get("fullConversationHeadersOnly", [])):
        if not isinstance(header, dict):
            continue
        bubble_id = header.get("bubbleId")
        if (
            not isinstance(bubble_id, str)
            or not bubble_id
            or bubble_id in generating_ids
        ):
            continue
        bubble = _read_cursor_json(
            transcript_path, f"bubbleId:{host_session_key}:{bubble_id}"
        )
        if not isinstance(bubble, dict):
            continue
        message = _normalize_cursor_message(
            bubble,
            composer_id=host_session_key,
            bubble_id=bubble_id,
            fallback_index=index,
        )
        if message is not None:
            events.append(message)
        events.extend(
            _normalize_cursor_tool_events(
                bubble,
                composer_id=host_session_key,
                bubble_id=bubble_id,
            )
        )
    return events


def extract_cursor_model_usage(
    *, host_session_key: str, transcript_path: Path
) -> list[dict[str, Any]]:
    """Extract per-bubble token usage from one Cursor global state database."""

    composer = _read_cursor_json(transcript_path, f"composerData:{host_session_key}")
    if not isinstance(composer, dict):
        raise FileNotFoundError(
            f"Cursor transcript source for session '{host_session_key}' could not be found."
        )

    generating_ids = {
        bubble_id
        for bubble_id in composer.get("generatingBubbleIds", [])
        if isinstance(bubble_id, str) and bubble_id
    }
    rows: list[dict[str, Any]] = []
    for header in composer.get("fullConversationHeadersOnly", []):
        if not isinstance(header, dict):
            continue
        bubble_id = header.get("bubbleId")
        if (
            not isinstance(bubble_id, str)
            or not bubble_id
            or bubble_id in generating_ids
        ):
            continue
        bubble = _read_cursor_json(
            transcript_path, f"bubbleId:{host_session_key}:{bubble_id}"
        )
        if not isinstance(bubble, dict):
            continue
        token_count = bubble.get("tokenCount")
        if not isinstance(token_count, dict):
            continue
        model_id = _cursor_model_id(bubble)
        rows.append(
            {
                "host_usage_key": str(
                    _first_string(
                        bubble, ("requestId", "responseId", "conversationRequestId")
                    )
                    or bubble_id
                ),
                "source_kind": "cursor_state_vscdb",
                "occurred_at": _timestamp_to_iso(bubble.get("createdAt")),
                "agent_role": "foreground",
                "provider": _provider_from_model_id(model_id),
                "model_id": model_id,
                "input_tokens": token_count.get(
                    "inputTokens", token_count.get("input_tokens")
                ),
                "output_tokens": token_count.get(
                    "outputTokens", token_count.get("output_tokens")
                ),
                "reasoning_output_tokens": token_count.get(
                    "reasoningOutputTokens", token_count.get("reasoning_output_tokens")
                ),
                "cached_input_tokens_total": token_count.get(
                    "cachedInputTokens", token_count.get("cached_input_tokens")
                ),
                "cache_read_input_tokens": token_count.get(
                    "cacheReadInputTokens", token_count.get("cache_read_input_tokens")
                ),
                "cache_creation_input_tokens": token_count.get(
                    "cacheCreationInputTokens",
                    token_count.get("cache_creation_input_tokens"),
                ),
                "capture_quality": "exact",
                "raw_usage_json": {
                    "tokenCount": token_count,
                    "bubbleId": bubble_id,
                },
            }
        )
    return rows


def _cursor_user_roots(search_roots: Sequence[Path]) -> list[Path]:
    """Normalize search roots into Cursor user roots."""

    roots: list[Path] = []
    for raw_root in search_roots:
        root = Path(raw_root).expanduser()
        if root.name == "state.vscdb" and root.parent.name == "globalStorage":
            roots.append(root.parent.parent.resolve())
            continue
        if root.name == "globalStorage":
            roots.append(root.parent.resolve())
            continue
        roots.append(root.resolve())
    return roots


def _connect_read_only(db_path: Path) -> sqlite3.Connection:
    """Open one Cursor SQLite database in read-only query-only mode."""

    uri = f"{db_path.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=2.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 2000")
    conn.execute("PRAGMA query_only = ON")
    return conn


def _read_cursor_json(
    db_path: Path, key: str, *, table: str = "cursorDiskKV"
) -> dict[str, Any] | None:
    """Read and decode one JSON object from one Cursor SQLite key-value table."""

    if not db_path.exists():
        return None
    try:
        with _connect_read_only(db_path) as conn:
            row = conn.execute(
                f"SELECT value FROM {table} WHERE key = ?", (key,)
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    value = row["value"]
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    if not isinstance(value, str):
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _cursor_db_has_composer(db_path: Path, composer_id: str) -> bool:
    """Return whether one Cursor global DB contains one composer payload."""

    return _read_cursor_json(db_path, f"composerData:{composer_id}") is not None


def _resolve_workspace_path(workspace_json_path: Path) -> Path | None:
    """Resolve the repo path from one Cursor workspace metadata file."""

    try:
        payload = json.loads(workspace_json_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    raw_uri = payload.get("folder") or payload.get("workspaceUri")
    if not isinstance(raw_uri, str) or not raw_uri:
        return None
    parsed = urlparse(raw_uri)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path)).expanduser()
    return Path(raw_uri).expanduser()


def _active_workspace_composer_ids(workspace_db: Path) -> list[str]:
    """Return active Cursor composer ids from one workspace state DB."""

    payload = _read_item_table_json(workspace_db, "composer.composerData")
    if not isinstance(payload, dict):
        return []
    ordered_ids: list[str] = []
    for raw_ids in (
        payload.get("selectedComposerIds"),
        payload.get("lastFocusedComposerIds"),
    ):
        if not isinstance(raw_ids, list):
            continue
        for composer_id in raw_ids:
            if (
                isinstance(composer_id, str)
                and composer_id
                and composer_id not in ordered_ids
            ):
                ordered_ids.append(composer_id)
    return ordered_ids


def _read_item_table_json(db_path: Path, key: str) -> dict[str, Any] | None:
    """Read one JSON object from Cursor's workspace ItemTable."""

    return _read_cursor_json(db_path, key, table="ItemTable")


def _composer_updated_at(composer: dict[str, Any], *, fallback_path: Path) -> float:
    """Return one host-neutral freshness marker for a Cursor composer."""

    for field in ("lastUpdatedAt", "updatedAt", "createdAt"):
        value = _timestamp_to_epoch_seconds(composer.get(field))
        if value is not None:
            return value
    return fallback_path.stat().st_mtime if fallback_path.exists() else 0.0


def _normalize_cursor_message(
    bubble: dict[str, Any],
    *,
    composer_id: str,
    bubble_id: str,
    fallback_index: int,
) -> dict[str, Any] | None:
    """Normalize one Cursor user or assistant bubble into one shared event payload."""

    source = _ROLE_BY_TYPE.get(bubble.get("type"))
    if source is None:
        return None
    text = _extract_cursor_text(bubble)
    if not text:
        return None
    host_event_key = bubble_id or f"cursor-bubble-{fallback_index}"
    return _build_event(
        composer_id=composer_id,
        host_event_key=host_event_key,
        source=source,
        occurred_at=_timestamp_to_iso(bubble.get("createdAt")),
        content_kind="message",
        content_text=text,
        raw_ref=f"cursor://composers/{composer_id}#bubble={bubble_id}",
    )


def _normalize_cursor_tool_events(
    bubble: dict[str, Any],
    *,
    composer_id: str,
    bubble_id: str,
) -> list[dict[str, Any]]:
    """Normalize meaningful Cursor tool artifacts into shared tool_result events."""

    events: list[dict[str, Any]] = []
    occurred_at = _timestamp_to_iso(bubble.get("createdAt"))

    for index, item in enumerate(_listify(bubble.get("toolResults"))):
        event = _build_cursor_tool_event(
            item=item,
            composer_id=composer_id,
            bubble_id=bubble_id,
            suffix=f"tool-result-{index}",
            occurred_at=occurred_at,
        )
        if event is not None:
            events.append(event)

    for index, item in enumerate(_listify(bubble.get("interpreterResults"))):
        event = _build_cursor_interpreter_event(
            item=item,
            composer_id=composer_id,
            bubble_id=bubble_id,
            suffix=f"interpreter-{index}",
            occurred_at=occurred_at,
        )
        if event is not None:
            events.append(event)

    diff_payload = bubble.get("assistantSuggestedDiffs")
    diff_items = _listify(diff_payload)
    if diff_items:
        summary = _cursor_diff_summary(diff_items)
        events.append(
            _build_tool_event(
                composer_id=composer_id,
                bubble_id=bubble_id,
                suffix="assistant-suggested-diff",
                occurred_at=occurred_at,
                tool_name="edit",
                status="ok",
                is_error=False,
                summary=summary,
                text=None,
                command=None,
            )
        )
    return events


def _build_cursor_tool_event(
    *,
    item: Any,
    composer_id: str,
    bubble_id: str,
    suffix: str,
    occurred_at: str,
) -> dict[str, Any] | None:
    """Build one normalized tool-result event from a generic Cursor toolResults item."""

    if not isinstance(item, dict):
        return None
    tool_name = _first_string(item, ("toolName", "tool_name", "name", "type"))
    status = _first_string(item, ("status", "state"))
    summary = _first_string(item, ("summary", "title", "resultSummary"))
    command = _first_string(item, ("command", "cmd"))
    text = _tool_payload_text(item)
    is_error = _infer_tool_error(item=item, text=text, status=status)
    if not should_keep_tool_result(
        tool_name=tool_name,
        status=status,
        text=text,
        summary=summary,
        command=command,
        is_error=is_error,
    ):
        return None
    return _build_tool_event(
        composer_id=composer_id,
        bubble_id=bubble_id,
        suffix=suffix,
        occurred_at=occurred_at,
        tool_name=tool_name,
        status=status,
        is_error=is_error,
        summary=summary,
        text=text,
        command=command,
    )


def _build_cursor_interpreter_event(
    *,
    item: Any,
    composer_id: str,
    bubble_id: str,
    suffix: str,
    occurred_at: str,
) -> dict[str, Any] | None:
    """Build one normalized tool-result event from one Cursor interpreter result."""

    if not isinstance(item, dict):
        return None
    command = _first_string(item, ("command", "cmd", "input"))
    text = _tool_payload_text(item)
    exit_code = item.get("exitCode")
    status = "error" if isinstance(exit_code, int) and exit_code != 0 else "ok"
    is_error = bool(isinstance(exit_code, int) and exit_code != 0)
    if not should_keep_tool_result(
        tool_name="exec_command",
        status=status,
        text=text,
        command=command,
        is_error=is_error,
    ):
        return None
    return _build_tool_event(
        composer_id=composer_id,
        bubble_id=bubble_id,
        suffix=suffix,
        occurred_at=occurred_at,
        tool_name="exec_command",
        status=status,
        is_error=is_error,
        summary=None,
        text=text,
        command=command,
    )


def _build_tool_event(
    *,
    composer_id: str,
    bubble_id: str,
    suffix: str,
    occurred_at: str,
    tool_name: str | None,
    status: str | None,
    is_error: bool,
    summary: str | None,
    text: str | None,
    command: str | None,
) -> dict[str, Any]:
    """Construct one shared Cursor tool_result event payload."""

    normalized_tool_name = _normalized_tool_name(tool_name=tool_name, command=command)
    normalized_status = (
        "error"
        if is_error
        else _normalized_tool_status(status=status, text=text, summary=summary)
    )
    return _build_event(
        composer_id=composer_id,
        host_event_key=f"{bubble_id}:tool:{suffix}",
        source="tool",
        occurred_at=occurred_at,
        content_kind="tool_result",
        content_text=summarize_tool_result(
            tool_name=normalized_tool_name,
            status=normalized_status,
            text=text,
            summary=summary,
            command=command,
            is_error=is_error,
        ),
        raw_ref=f"cursor://composers/{composer_id}#bubble={bubble_id}:tool={suffix}",
        extra_fields={
            "tool_name": normalized_tool_name,
            "status": normalized_status,
            "is_error": normalized_status == "error",
        },
    )


def _extract_cursor_text(bubble: dict[str, Any]) -> str:
    """Extract visible text from one Cursor bubble."""

    text = bubble.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    return _flatten_rich_text(bubble.get("richText"))


def _flatten_rich_text(rich_text: Any) -> str:
    """Flatten Cursor's rich-text payload into plain text when possible."""

    if isinstance(rich_text, str):
        rich_text = rich_text.strip()
        if not rich_text:
            return ""
        try:
            rich_text = json.loads(rich_text)
        except json.JSONDecodeError:
            return rich_text
    parts: list[str] = []
    _collect_rich_text_parts(rich_text, parts)
    return "\n".join(part for part in parts if part).strip()


def _collect_rich_text_parts(value: Any, parts: list[str]) -> None:
    """Collect text leaves from a nested Cursor rich-text payload."""

    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            parts.append(stripped)
        return
    if isinstance(value, list):
        for item in value:
            _collect_rich_text_parts(item, parts)
        return
    if not isinstance(value, dict):
        return
    text = value.get("text")
    if isinstance(text, str) and text.strip():
        parts.append(text.strip())
    for child_key in ("children", "root"):
        child = value.get(child_key)
        if child is not None:
            _collect_rich_text_parts(child, parts)


def _listify(value: Any) -> list[Any]:
    """Normalize one possibly-singular Cursor payload into a list."""

    if isinstance(value, list):
        return value
    if value is None or value == "" or value == ():
        return []
    return [value]


def _tool_payload_text(item: dict[str, Any]) -> str | None:
    """Extract compact human-readable text from one tool payload."""

    for key in ("text", "output", "summary", "stderr", "stdout", "result"):
        value = item.get(key)
        text = _stringify_tool_value(value)
        if text:
            return text
    return None


def _stringify_tool_value(value: Any) -> str | None:
    """Flatten one nested tool payload value into text."""

    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [part for item in value if (part := _stringify_tool_value(item))]
        return "\n".join(parts).strip() or None
    if isinstance(value, dict):
        parts = [
            part
            for key in (
                "text",
                "content",
                "message",
                "output",
                "stderr",
                "stdout",
                "summary",
            )
            if (part := _stringify_tool_value(value.get(key)))
        ]
        if parts:
            return "\n".join(parts).strip() or None
        try:
            return json.dumps(value, sort_keys=True)
        except TypeError:
            return None
    return None


def _first_string(item: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """Return the first non-empty string value from one mapping."""

    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _infer_tool_error(
    *, item: dict[str, Any], text: str | None, status: str | None
) -> bool:
    """Infer whether one generic Cursor tool result represents an error."""

    if bool(item.get("isError")) or bool(item.get("is_error")):
        return True
    exit_code = item.get("exitCode")
    if isinstance(exit_code, int) and exit_code != 0:
        return True
    lowered_status = (status or "").strip().lower()
    if lowered_status in {"error", "failed", "failure"}:
        return True
    lowered_text = (text or "").lower()
    return any(token in lowered_text for token in ("failed", "error", "exception"))


def _cursor_diff_summary(diff_items: list[Any]) -> str:
    """Return one durable summary for assistant-suggested diffs."""

    first_path = None
    for item in diff_items:
        if not isinstance(item, dict):
            continue
        first_path = _first_string(item, ("relativePath", "path", "filePath", "uri"))
        if first_path:
            break
    if first_path is not None and len(diff_items) == 1:
        return f"updated {first_path}"
    if first_path is not None:
        return f"updated {first_path} and {len(diff_items) - 1} more file(s)"
    return "updated file"


def _build_event(
    *,
    composer_id: str,
    host_event_key: str,
    source: str,
    occurred_at: str,
    content_kind: str,
    content_text: str,
    raw_ref: str,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct one shared normalized Cursor event payload."""

    event = {
        "host_app": "cursor",
        "host_session_key": composer_id,
        "host_event_key": host_event_key,
        "source": source,
        "occurred_at": occurred_at,
        "content_kind": content_kind,
        "content_text": content_text,
        "raw_ref": raw_ref,
    }
    if extra_fields:
        event.update(extra_fields)
    return event


def _normalized_tool_name(*, tool_name: str | None, command: str | None) -> str:
    """Normalize Cursor tool identifiers into stable analytics-friendly names."""

    if isinstance(tool_name, str) and tool_name:
        lowered = tool_name.strip().lower()
        if lowered in {"bash", "terminal", "runterminalcommand"}:
            return "exec_command"
        return lowered
    if command is not None:
        return "exec_command"
    return "exec_command"


def _normalized_tool_status(
    *, status: str | None, text: str | None, summary: str | None
) -> str:
    """Infer a stable ok/error status for Cursor tool results."""

    lowered_status = (status or "").strip().lower()
    if lowered_status in {"error", "failed", "failure"}:
        return "error"
    lowered_text = f"{text or ''}\n{summary or ''}".lower()
    if any(token in lowered_text for token in ("failed", "error", "exception")):
        return "error"
    return "ok"


def _timestamp_to_epoch_seconds(value: Any) -> float | None:
    """Convert one Cursor timestamp into epoch seconds when possible."""

    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric / 1000.0 if numeric > 10_000_000_000 else numeric
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.astimezone(timezone.utc).timestamp()
    return None


def _timestamp_to_iso(value: Any) -> str:
    """Convert one Cursor timestamp into a stable ISO-8601 UTC string."""

    epoch_seconds = _timestamp_to_epoch_seconds(value)
    if epoch_seconds is None:
        return ""
    return (
        datetime.fromtimestamp(epoch_seconds, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _cursor_model_id(bubble: dict[str, Any]) -> str | None:
    """Extract one model identifier from a Cursor bubble when present."""

    direct = _first_string(bubble, ("model", "modelId"))
    if direct is not None:
        return direct
    model_info = bubble.get("modelInfo")
    if isinstance(model_info, dict):
        return _first_string(model_info, ("id", "model", "modelId"))
    return None


def _provider_from_model_id(model_id: str | None) -> str | None:
    """Infer the model provider from one Cursor-exposed model identifier."""

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


def sys_platform_linux() -> bool:
    """Return whether the current platform uses the Linux-style Cursor home."""

    return os.name != "nt" and "linux" in os.sys.platform
