"""Deterministic filtering and summarization for host tool-result events."""

from __future__ import annotations

import re
import shlex


_NOISY_TOOLS = {"glob", "read", "grep", "search", "find", "ls", "pwd", "cat"}
_MUTATION_TOOLS = {"edit", "write", "multiedit", "apply_patch"}
_VALIDATION_FAMILIES = {
    "pytest",
    "py.test",
    "go test",
    "cargo test",
    "npm test",
    "pnpm test",
    "yarn test",
    "alembic",
}
_NOISY_COMMANDS = {"ls", "pwd", "cat", "rg", "grep", "find", "fd", "head", "tail", "sed"}
_FAILED_PREFIXES = ("failed", "error", "exception")
_MUTATION_PREFIXES = ("updated", "edited", "patched", "applied", "wrote")


def should_keep_tool_result(
    *,
    tool_name: str | None,
    status: str | None,
    text: str | None,
    summary: str | None = None,
    command: str | None = None,
    is_error: bool | None = None,
) -> bool:
    """Return whether one tool result carries durable episodic value."""

    normalized_tool = (tool_name or "").strip().lower()
    normalized_command = _command_family(command)
    normalized_status = (status or "").strip().lower()
    normalized_summary = (summary or "").strip().lower()
    normalized_text = _compact_text(text).lower()

    if is_error is True or normalized_status in {"error", "failed", "failure"}:
        return True
    if _extract_exit_code(text) not in {None, 0}:
        return True
    if normalized_tool in _MUTATION_TOOLS:
        return True
    if normalized_command in _VALIDATION_FAMILIES:
        return True
    if normalized_summary.startswith(_FAILED_PREFIXES) or normalized_summary.startswith(_MUTATION_PREFIXES):
        return True
    if normalized_text.startswith(_FAILED_PREFIXES) or normalized_text.startswith(_MUTATION_PREFIXES):
        return True
    if normalized_tool in _NOISY_TOOLS:
        return False
    if normalized_command in _NOISY_COMMANDS:
        return False
    return False


def summarize_tool_result(
    *,
    tool_name: str | None,
    status: str | None,
    text: str | None,
    summary: str | None = None,
    command: str | None = None,
    is_error: bool | None = None,
) -> str:
    """Build a compact, stable human-readable tool result summary."""

    command_family = _command_family(command)
    exit_code = _extract_exit_code(text)

    if summary:
        return _normalize_summary(summary)
    if command_family in _VALIDATION_FAMILIES:
        if is_error is True or (status or "").lower() in {"error", "failed", "failure"} or exit_code not in {None, 0}:
            return f"{command_family} failed"
        return f"{command_family} passed"

    compact_text = _compact_text(text)
    if compact_text:
        return _normalize_summary(compact_text)
    normalized_tool = (tool_name or "tool").strip().lower()
    if normalized_tool in _MUTATION_TOOLS:
        return f"{normalized_tool} updated file"
    if is_error is True or (status or "").lower() in {"error", "failed", "failure"}:
        return f"{normalized_tool} failed"
    return f"{normalized_tool} completed"


def _normalize_summary(value: str) -> str:
    """Collapse one tool result into a short stable sentence fragment."""

    compact = _compact_text(value)
    lowered = compact.lower()
    if ":" in compact:
        prefix = compact.split(":", 1)[0].strip()
        lowered_prefix = prefix.lower()
        if (
            any(token in lowered_prefix for token in ("failed", "error", "exception"))
            or lowered_prefix.startswith(_MUTATION_PREFIXES)
        ):
            return prefix
    if lowered.startswith("process exited with code"):
        return compact.splitlines()[0].strip()
    return compact


def _compact_text(value: str | None) -> str:
    """Drop wrapper noise and keep the first meaningful output line."""

    if value is None:
        return ""
    for line in value.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("Chunk ID:"):
            continue
        if stripped.startswith("Wall time:"):
            continue
        if stripped.startswith("Original token count:"):
            continue
        if stripped == "Output:":
            continue
        return stripped
    return ""


def _command_family(command: str | None) -> str:
    """Reduce one shell command into a stable family label when possible."""

    if not command:
        return ""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    if not tokens:
        return ""
    lowered = [token.lower() for token in tokens]
    head = lowered[0]
    if head in {"python", "python3", "uv"} and len(lowered) >= 3 and lowered[1] == "-m":
        return f"{lowered[1]} {lowered[2]}"
    if head == "go" and len(lowered) >= 2:
        return f"go {lowered[1]}"
    if head == "cargo" and len(lowered) >= 2:
        return f"cargo {lowered[1]}"
    if head in {"npm", "pnpm", "yarn"} and len(lowered) >= 2:
        return f"{head} {lowered[1]}"
    return head


def _extract_exit_code(text: str | None) -> int | None:
    """Extract one exit status from wrapped shell output when present."""

    if text is None:
        return None
    match = re.search(r"Process exited with code (\d+)", text)
    if match is None:
        return None
    return int(match.group(1))
