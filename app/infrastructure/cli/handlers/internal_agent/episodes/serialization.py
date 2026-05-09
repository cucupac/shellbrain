"""Serialization helpers for agent operation responses."""

from __future__ import annotations

import json


def serialize_episode_event(event) -> dict:
    """Render one stored episode event into deterministic JSON-safe output."""

    content = str(event.content)
    try:
        parsed_content = json.loads(content)
    except json.JSONDecodeError:
        parsed_content = content
    created_at = event.created_at.isoformat() if event.created_at is not None else None
    return {
        "id": event.id,
        "seq": event.seq,
        "source": event.source.value
        if hasattr(event.source, "value")
        else str(event.source),
        "content": parsed_content,
        "created_at": created_at,
    }
