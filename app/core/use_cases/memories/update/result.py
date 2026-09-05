"""Result types for the memory update use case."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.use_cases.memories.writes import MemoryWrite


@dataclass(frozen=True)
class UpdateMemoryResult:
    """Typed single-memory update result with completed write metadata."""

    memory_id: str
    writes: list[MemoryWrite]

    def to_response_data(self) -> dict[str, object]:
        return {"memory_id": self.memory_id}


@dataclass(frozen=True)
class BatchUpdateMemoryResult:
    """Typed batch memory update result with completed write metadata."""

    problem_id: str
    updated_memory_ids: list[str]
    applied_count: int
    writes: list[MemoryWrite]

    def to_response_data(self) -> dict[str, object]:
        return {
            "problem_id": self.problem_id,
            "updated_memory_ids": self.updated_memory_ids,
            "applied_count": self.applied_count,
        }
