"""Repository summaries used by cross-repo read surfaces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RepositorySummary:
    """Compact read-only summary for one Shellbrain repository."""

    repo_id: str
    repo_root: str | None
    concept_count: int
    memory_count: int
    evidence_count: int
    last_seen_at: str | None
