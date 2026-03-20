"""Guidance entities used to nudge agents without adding new top-level commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, kw_only=True)
class PendingUtilityCandidate:
    """One memory that still appears to need a utility vote for the active problem."""

    memory_id: str
    kind: str
    retrieval_count: int
    last_seen_at: str


@dataclass(frozen=True, kw_only=True)
class GuidanceDecision:
    """One guidance item that may be attached to a successful operation result."""

    code: str
    severity: str
    message: str
    problem_id: str | None = None
    memory_ids: list[str] = field(default_factory=list)
    vote_scale_hint: dict[str, float] | None = None
    setup_hint: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialize one guidance decision into the public response shape."""

        payload: dict[str, Any] = {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.problem_id is not None:
            payload["problem_id"] = self.problem_id
        if self.memory_ids:
            payload["memory_ids"] = list(self.memory_ids)
        if self.vote_scale_hint is not None:
            payload["vote_scale_hint"] = dict(self.vote_scale_hint)
        if self.setup_hint is not None:
            payload["setup_hint"] = self.setup_hint
        return payload
