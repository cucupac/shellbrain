"""Result types for scenario recording."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.entities.scenarios import ScenarioOutcome


@dataclass(frozen=True)
class ScenarioRecordResult:
    """Typed result for one scenario-record command."""

    scenario_id: str
    outcome: ScenarioOutcome
    created: bool

    @property
    def data(self) -> dict[str, object]:
        return self.to_response_data()

    def to_response_data(self) -> dict[str, object]:
        """Return the stable CLI response payload."""

        return {
            "scenario_id": self.scenario_id,
            "outcome": self.outcome.value,
            "created": self.created,
        }
