"""Result types for the concept show use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConceptShowResult:
    """Typed concept-show result."""

    concept: dict[str, Any]

    @property
    def data(self) -> dict[str, object]:
        return {"concept": self.concept}

    def to_response_data(self) -> dict[str, object]:
        return self.data
