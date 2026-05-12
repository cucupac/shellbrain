"""Structured output parsing for inner-agent provider responses."""

from __future__ import annotations

import json
from typing import Any


class InnerAgentOutputParseError(ValueError):
    """Raised when provider output is not valid inner-agent JSON."""


def parse_inner_agent_brief_output(output: str) -> dict[str, Any]:
    """Parse a provider final response into a worker brief object."""

    brief, _requested_expansions = parse_inner_agent_response_output(output)
    if brief is None:
        raise InnerAgentOutputParseError("inner-agent output must include a brief")
    return brief


def parse_inner_agent_response_output(
    output: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Parse provider output into either a final brief or expansion requests."""

    text = _strip_code_fence(output.strip())
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InnerAgentOutputParseError("inner-agent output is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise InnerAgentOutputParseError("inner-agent output must be a JSON object")

    requested_expansions = _requested_expansions(payload.get("requested_expansions"))
    brief = payload.get("brief")
    if brief is None and "summary" in payload:
        brief = payload
    if not isinstance(brief, dict):
        if requested_expansions:
            return None, requested_expansions
        raise InnerAgentOutputParseError("inner-agent output must include an object brief")
    if not isinstance(brief.get("summary"), str) or not brief["summary"].strip():
        raise InnerAgentOutputParseError("inner-agent brief.summary is required")
    return brief, requested_expansions


def _requested_expansions(value: Any) -> list[dict[str, Any]]:
    """Return dict expansion requests from provider output."""

    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


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
