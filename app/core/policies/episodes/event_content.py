"""Pure serialization rules for normalized episode-event content."""

from __future__ import annotations

import json

from app.core.use_cases.episodes.sync_episode.request import NormalizedEpisodeEvent


def serialize_normalized_episode_event(event: NormalizedEpisodeEvent) -> str:
    """Return deterministic JSON content for one normalized episode event."""

    return json.dumps(
        event.to_content_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
