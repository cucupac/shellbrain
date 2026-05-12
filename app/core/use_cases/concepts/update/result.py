"""Result types for the concept update use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConceptUpdateResult:
    """Typed concept-update result."""

    updated_count: int
    results: list[dict[str, Any]]

    @property
    def data(self) -> dict[str, object]:
        return {"updated_count": self.updated_count, "results": self.results}

    def to_response_data(self) -> dict[str, object]:
        return self.data
