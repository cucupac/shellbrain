"""Claude Code transcript discovery and normalization helpers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
import hashlib
import json
from pathlib import Path
from typing import Any

from app.periphery.episodes.tool_filter import should_keep_tool_result, summarize_tool_result


def resolve_claude_code_transcript_path(
    *,
    host_session_key: str,
    search_roots: Sequence[Path],
    last_known_path: Path | None = None,
) -> Path:
    """Resolve one Claude Code transcript path from a CLI session id."""

    if last_known_path is not None and last_known_path.exists():
        return last_known_path

    for root in search_roots:
        if not root.exists():
            continue
        for metadata_path in _iter_metadata_files(root):
            metadata = _read_metadata(metadata_path)
            if metadata.get("cliSessionId") != host_session_key:
                continue
            transcript_path = _transcript_path_for_metadata(root=root, metadata=metadata)
            if transcript_path.exists():
                return transcript_path

    for root in search_roots:
        if not root.exists():
            continue
        matches = sorted(root.rglob(f"{host_session_key}.jsonl"))
        if matches:
            return max(matches, key=lambda path: path.stat().st_mtime)

    raise FileNotFoundError(
        f"Claude Code transcript source for session '{host_session_key}' could not be found."
    )


def find_latest_claude_code_session_for_repo(
    *,
    repo_root: Path,
    search_roots: Sequence[Path],
) -> dict[str, Any] | None:
    """Return the most recently updated Claude Code session for one repo root."""

    candidates: list[dict[str, Any]] = []
    resolved_repo_root = repo_root.resolve()
    for root in search_roots:
        if not root.exists():
            continue
        for metadata_path in _iter_metadata_files(root):
            metadata = _read_metadata(metadata_path)
            cwd = metadata.get("cwd")
            cli_session_id = metadata.get("cliSessionId")
            if not isinstance(cwd, str) or not isinstance(cli_session_id, str):
                continue
            try:
                if Path(cwd).resolve() != resolved_repo_root:
                    continue
            except FileNotFoundError:
                continue
            transcript_path = _transcript_path_for_metadata(root=root, metadata=metadata)
            if not transcript_path.exists():
                continue
            candidates.append(
                {
                    "host_app": "claude_code",
                    "host_session_key": cli_session_id,
                    "transcript_path": transcript_path,
                    "updated_at": transcript_path.stat().st_mtime,
                }
            )
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate["updated_at"])


def normalize_claude_code_transcript(
    *,
    host_session_key: str,
    transcript_path: Path,
) -> list[dict[str, Any]]:
    """Normalize one Claude Code transcript into shared compact event dictionaries."""

    events: list[dict[str, Any]] = []
    tool_uses: dict[str, dict[str, Any]] = {}

    with transcript_path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            raw_line = raw_line.rstrip("\n")
            if not raw_line:
                continue
            payload = json.loads(raw_line)
            line_type = payload.get("type")
            message = payload.get("message", {})
            content = message.get("content")

            if line_type == "assistant":
                tool_uses.update(_collect_tool_uses(content))
                text = _extract_claude_text(content)
                if text:
                    events.append(
                        _build_event(
                            host_session_key=host_session_key,
                            host_event_key=_fallback_key(payload, raw_line, line_number),
                            source="assistant",
                            occurred_at=str(payload.get("timestamp") or ""),
                            content_kind="message",
                            content_text=text,
                        )
                    )
                continue

            if line_type == "user":
                text = _extract_user_text_message(payload)
                if text:
                    events.append(
                        _build_event(
                            host_session_key=host_session_key,
                            host_event_key=_fallback_key(payload, raw_line, line_number),
                            source="user",
                            occurred_at=str(payload.get("timestamp") or ""),
                            content_kind="message",
                            content_text=text,
                        )
                    )
                for tool_event in _normalize_tool_results(
                    payload,
                    host_session_key=host_session_key,
                    raw_line=raw_line,
                    line_number=line_number,
                    tool_uses=tool_uses,
                ):
                    events.append(tool_event)

    return events


def _read_metadata(metadata_path: Path) -> dict[str, Any]:
    """Read one Claude Code local session metadata file."""

    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _iter_metadata_files(root: Path) -> Iterable[Path]:
    """Yield Claude Code local-session metadata files from bounded search roots."""

    direct_root = root / "Library" / "Application Support" / "Claude" / "claude-code-sessions"
    if direct_root.exists():
        yield from direct_root.rglob("local_*.json")
        return
    yield from root.rglob("local_*.json")


def _transcript_path_for_metadata(*, root: Path, metadata: dict[str, Any]) -> Path:
    """Resolve the transcript path described by one Claude Code metadata file."""

    cwd = metadata.get("cwd")
    cli_session_id = metadata.get("cliSessionId")
    if not isinstance(cwd, str) or not isinstance(cli_session_id, str):
        return root / "__missing__"
    return root / ".claude" / "projects" / _encode_cwd(cwd) / f"{cli_session_id}.jsonl"


def _encode_cwd(cwd: str) -> str:
    """Match Claude Code's cwd-to-project-folder encoding."""

    return cwd.replace("/", "-")


def _collect_tool_uses(content: Any) -> dict[str, dict[str, Any]]:
    """Extract tool-use metadata from one assistant content block."""

    collected: dict[str, dict[str, Any]] = {}
    if not isinstance(content, Iterable) or isinstance(content, (str, bytes)):
        return collected
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "tool_use":
            continue
        tool_id = item.get("id")
        if isinstance(tool_id, str):
            collected[tool_id] = item
    return collected


def _extract_claude_text(content: Any) -> str:
    """Extract visible text items from one Claude Code message content block."""

    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, Iterable) or isinstance(content, (str, bytes)):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "text":
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts).strip()


def _extract_user_text_message(payload: dict[str, Any]) -> str:
    """Extract a user-authored Claude Code message while skipping tool-result wrappers."""

    message = payload.get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, Iterable) or isinstance(content, (str, bytes)):
        return ""
    if any(isinstance(item, dict) and item.get("type") == "tool_result" for item in content):
        return ""
    return _extract_claude_text(content)


def _normalize_tool_results(
    payload: dict[str, Any],
    *,
    host_session_key: str,
    raw_line: str,
    line_number: int,
    tool_uses: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize all meaningful tool results carried in one Claude Code user record."""

    message = payload.get("message", {})
    content = message.get("content")
    if not isinstance(content, Iterable) or isinstance(content, (str, bytes)):
        return []

    events: list[dict[str, Any]] = []
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "tool_result":
            continue
        tool_use_id = item.get("tool_use_id")
        tool_use = tool_uses.get(str(tool_use_id)) if isinstance(tool_use_id, str) else None
        tool_name = tool_use.get("name") if isinstance(tool_use, dict) else None
        command = _tool_command(tool_use)
        is_error = bool(item.get("is_error"))
        text = _tool_result_text(item)
        if not should_keep_tool_result(
            tool_name=tool_name if isinstance(tool_name, str) else None,
            status="error" if is_error else "ok",
            text=text,
            command=command,
            is_error=is_error,
        ):
            continue
        host_event_key = str(payload.get("uuid") or _fallback_key(payload, raw_line, line_number))
        if isinstance(tool_use_id, str):
            host_event_key = tool_use_id
        events.append(
            _build_event(
                host_session_key=host_session_key,
                host_event_key=host_event_key,
                source="tool",
                occurred_at=str(payload.get("timestamp") or ""),
                content_kind="tool_result",
                content_text=summarize_tool_result(
                    tool_name=tool_name if isinstance(tool_name, str) else None,
                    status="error" if is_error else "ok",
                    text=text,
                    command=command,
                    is_error=is_error,
                ),
            )
        )
    return events


def _tool_command(tool_use: dict[str, Any] | None) -> str | None:
    """Extract a shell command from a Claude Code tool use when present."""

    if not isinstance(tool_use, dict):
        return None
    name = tool_use.get("name")
    if name != "Bash":
        return None
    input_payload = tool_use.get("input", {})
    if not isinstance(input_payload, dict):
        return None
    command = input_payload.get("command")
    return command if isinstance(command, str) else None


def _tool_result_text(item: dict[str, Any]) -> str | None:
    """Extract tool-result text from Claude Code's multiple result layouts."""

    text = item.get("text")
    if isinstance(text, str):
        return text
    content = item.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [piece.get("text", "") for piece in content if isinstance(piece, dict)]
        if parts:
            return "\n".join(part for part in parts if part)
    return None


def _build_event(
    *,
    host_session_key: str,
    host_event_key: str,
    source: str,
    occurred_at: str,
    content_kind: str,
    content_text: str,
) -> dict[str, Any]:
    """Construct one shared normalized Claude Code event payload."""

    return {
        "host_app": "claude_code",
        "host_session_key": host_session_key,
        "host_event_key": host_event_key,
        "source": source,
        "occurred_at": occurred_at,
        "content_kind": content_kind,
        "content_text": content_text,
        "raw_ref": f"claude_code://sessions/{host_session_key}#event={host_event_key}",
    }


def _fallback_key(payload: dict[str, Any], raw_line: str, line_number: int) -> str:
    """Build a stable upstream event key when Claude Code does not expose one directly."""

    explicit = payload.get("uuid")
    if isinstance(explicit, str) and explicit:
        return explicit
    digest = hashlib.sha1(raw_line.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    return f"claude-line-{line_number}-{digest}"
