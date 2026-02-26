"""This module defines deterministic JSON presentation helpers for CLI responses."""

import json
from typing import Any


def render(payload: dict[str, Any]) -> str:
    """This function renders payloads as deterministic sorted JSON output."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
