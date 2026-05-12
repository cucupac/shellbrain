"""Result types for the worker-facing recall use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RecallMemoryResult:
    """Typed recall result with telemetry kept out of the public response."""

    brief: dict[str, Any]
    fallback_reason: str | None
    telemetry: dict[str, Any]

    @property
    def data(self) -> dict[str, object]:
        return {
            "brief": self.brief,
            "fallback_reason": self.fallback_reason,
            "_telemetry": self.telemetry,
        }

    def to_response_data(self) -> dict[str, object]:
        return {
            "brief": self.brief,
            "fallback_reason": self.fallback_reason,
        }
