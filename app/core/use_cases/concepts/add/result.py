"""Result types for the concept add use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConceptAddResult:
    """Typed concept-add result."""

    added_count: int
    results: list[dict[str, Any]]

    @property
    def data(self) -> dict[str, object]:
        return {"added_count": self.added_count, "results": self.results}

    def to_response_data(self) -> dict[str, object]:
        return self.data
