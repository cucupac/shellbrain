"""This module defines deterministic JSON presentation helpers for CLI responses."""

import json
from typing import Any


def render(payload: dict[str, Any]) -> str:
    """This function renders payloads as deterministic compact JSON output."""

    return json.dumps(payload, separators=(",", ":"))
