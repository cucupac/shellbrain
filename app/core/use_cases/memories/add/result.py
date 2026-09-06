"""Result types for the memory add use case."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.use_cases.memories.writes import MemoryWrite


@dataclass(frozen=True)
class CreateMemoryResult:
    """Typed memory-add result with completed write metadata."""

    memory_id: str
    writes: list[MemoryWrite]

    @property
    def data(self) -> dict[str, object]:
        return {
            "memory_id": self.memory_id,
        }

    def to_response_data(self) -> dict[str, object]:
        return {"memory_id": self.memory_id}
