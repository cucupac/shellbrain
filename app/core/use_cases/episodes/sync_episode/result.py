"""Result types for syncing one host episode."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SyncEpisodeResult:
    """Typed summary of one episode sync."""

    episode_id: str
    thread_id: str
    imported_event_count: int
    transcript_path: str
    total_event_count: int
    user_event_count: int
    assistant_event_count: int
    tool_event_count: int
    system_event_count: int
    tool_type_counts: dict[str, int]

    def to_response_data(self) -> dict[str, object]:
        return {
            "episode_id": self.episode_id,
            "thread_id": self.thread_id,
            "imported_event_count": self.imported_event_count,
            "transcript_path": self.transcript_path,
            "total_event_count": self.total_event_count,
            "user_event_count": self.user_event_count,
            "assistant_event_count": self.assistant_event_count,
            "tool_event_count": self.tool_event_count,
            "system_event_count": self.system_event_count,
            "tool_type_counts": self.tool_type_counts,
        }
