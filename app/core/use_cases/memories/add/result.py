"""Result types for the memory add use case."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.use_cases.memories.effect_plan import PlannedEffect


@dataclass(frozen=True)
class CreatePlanIds:
    """IDs preallocated by the create use case before pure planning."""

    memory_id: str
    association_edge_ids: tuple[str, ...] = ()
    association_observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CreateMemoryResult:
    """Typed memory-add result with internal effect metadata."""

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
