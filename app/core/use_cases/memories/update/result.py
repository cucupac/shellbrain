"""Result types for the memory update use case."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.use_cases.memories.effect_plan import PlannedEffect


@dataclass(frozen=True)
class UpdatePlanIds:
    """IDs preallocated by the update use case before pure planning."""

    utility_observation_id: str | None = None
    fact_update_id: str | None = None
    association_edge_id: str | None = None
    association_observation_id: str | None = None


@dataclass(frozen=True)
class UpdateMemoryResult:
    """Typed single-memory update result with internal effect metadata."""

    memory_id: str
    planned_effects: list[PlannedEffect]

    @property
    def data(self) -> dict[str, object]:
        return {
            "memory_id": self.memory_id,
            "planned_side_effects": self.planned_effects,
        }

    def to_response_data(self) -> dict[str, object]:
        return {"memory_id": self.memory_id}


@dataclass(frozen=True)
class BatchUpdateMemoryResult:
    """Typed batch memory update result with internal effect metadata."""

    problem_id: str
    updated_memory_ids: list[str]
    applied_count: int
    planned_effects: list[PlannedEffect]

    @property
    def data(self) -> dict[str, object]:
        return {
            "problem_id": self.problem_id,
            "updated_memory_ids": self.updated_memory_ids,
            "applied_count": self.applied_count,
            "planned_side_effects": self.planned_effects,
        }

    def to_response_data(self) -> dict[str, object]:
        return {
            "problem_id": self.problem_id,
            "updated_memory_ids": self.updated_memory_ids,
            "applied_count": self.applied_count,
        }
