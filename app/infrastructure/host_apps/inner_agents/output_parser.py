"""Structured output parsing for inner-agent provider responses."""

from __future__ import annotations

import json
from typing import Any


class InnerAgentOutputParseError(ValueError):
    """Raised when provider output is not valid inner-agent JSON."""


def parse_inner_agent_brief_output(output: str) -> dict[str, Any]:
    """Parse a provider final response into a worker brief object."""

    text = _strip_code_fence(output.strip())
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InnerAgentOutputParseError("inner-agent output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise InnerAgentOutputParseError("inner-agent output must be a JSON object")

    brief = payload.get("brief")
    if not isinstance(brief, dict):
        raise InnerAgentOutputParseError("inner-agent output must include an object brief")
    if not isinstance(brief.get("summary"), str) or not brief["summary"].strip():
        raise InnerAgentOutputParseError("inner-agent brief.summary is required")
    return brief


def parse_build_knowledge_output(output: str) -> dict[str, Any]:
    """Parse provider output for one build_knowledge run."""

    text = _strip_code_fence(output.strip())
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InnerAgentOutputParseError("build_knowledge output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise InnerAgentOutputParseError("build_knowledge output must be a JSON object")

    status = str(payload.get("status") or "ok").strip()
    if status not in {"ok", "skipped"}:
        raise InnerAgentOutputParseError("build_knowledge status must be ok or skipped")
    run_summary = payload.get("run_summary")
    if not isinstance(run_summary, str) or not run_summary.strip():
        raise InnerAgentOutputParseError("build_knowledge run_summary is required")

    write_count = _nonnegative_int(payload.get("write_count"))
    if write_count is None:
        write_count = _count_write_commands(payload)
    skipped_items = payload.get("skipped_items")
    skipped_item_count = len(skipped_items) if isinstance(skipped_items, list) else 0
    read_trace = payload.get("read_trace")
    code_trace = payload.get("code_trace")
    return {
        "status": status,
        "run_summary": run_summary.strip(),
        "write_count": write_count,
        "skipped_item_count": skipped_item_count,
        "read_trace": read_trace if isinstance(read_trace, dict) else {},
        "code_trace": code_trace if isinstance(code_trace, dict) else {},
    }


def _nonnegative_int(value: Any) -> int | None:
    """Return a non-negative integer or None when absent/malformed."""

    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def _count_write_commands(payload: dict[str, Any]) -> int:
    """Derive a conservative write count from reported command traces."""

    count = 0
    for trace_key in ("read_trace", "write_trace"):
        trace = payload.get(trace_key)
        if not isinstance(trace, dict):
            continue
        commands = trace.get("commands")
        if not isinstance(commands, list):
            continue
        for command in commands:
            text = _command_text(command)
            if text.startswith(("shellbrain memory add", "shellbrain memory update")):
                count += 1
            elif text.startswith(("shellbrain concept add", "shellbrain concept update")):
                count += 1
            elif text.startswith("shellbrain scenario record"):
                count += 1
    return count


def _command_text(value: Any) -> str:
    """Return one normalized command string."""

    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        command = value.get("command")
        if isinstance(command, list):
            return " ".join(str(part) for part in command).strip()
        return str(command or "").strip()
    return ""


def _strip_code_fence(text: str) -> str:
    """Remove a single Markdown JSON code fence when present."""

    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        first = lines[0].strip().lower()
        if first in {"```", "```json"}:
            return "\n".join(lines[1:-1]).strip()
    return text
