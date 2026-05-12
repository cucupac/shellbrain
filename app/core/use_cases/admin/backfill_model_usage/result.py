"""Result types for model-usage backfill."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackfillSummary:
    """Small structured summary for token-usage backfill runs."""

    sessions_examined: int
    sessions_with_records: int
    sessions_skipped: int
    sessions_failed: int
    records_attempted: int
    host_counts: dict[str, int]
    errors: list[dict[str, str]]

    def to_payload(self) -> dict[str, object]:
        """Render the summary into JSON-safe primitives."""

        return {
            "sessions_examined": self.sessions_examined,
            "sessions_with_records": self.sessions_with_records,
            "sessions_skipped": self.sessions_skipped,
            "sessions_failed": self.sessions_failed,
            "records_attempted": self.records_attempted,
            "host_counts": self.host_counts,
            "errors": self.errors,
        }
