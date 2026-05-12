"""Result types for the memory read use case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReadMemoryResult:
    """Typed read result."""

    pack: dict[str, Any]

    @property
    def data(self) -> dict[str, object]:
        return {"pack": self.pack}

    def to_response_data(self) -> dict[str, object]:
        return {"pack": self.pack}
