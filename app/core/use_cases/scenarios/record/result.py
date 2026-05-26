"""Result types for scenario recording."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.entities.scenarios import ScenarioOutcome


@dataclass(frozen=True)
class SolutionDeltaRecordResult:
    """Result of automatic snapshot-backed delta attachment."""

    status: str
    solution_delta_id: str | None = None
    base_snapshot_id: str | None = None
    final_snapshot_id: str | None = None
    patch_sha: str | None = None
    changed_paths: tuple[str, ...] = ()
    reason: str | None = None

    def to_response_data(self) -> dict[str, object]:
        """Return the stable CLI response payload."""

        return {
            "status": self.status,
            "solution_delta_id": self.solution_delta_id,
            "base_snapshot_id": self.base_snapshot_id,
            "final_snapshot_id": self.final_snapshot_id,
            "patch_sha": self.patch_sha,
            "changed_paths": list(self.changed_paths),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ScenarioRecordResult:
    """Typed result for one scenario-record command."""

    scenario_id: str
    outcome: ScenarioOutcome
    created: bool
    solution_delta: SolutionDeltaRecordResult | None = None

    @property
    def data(self) -> dict[str, object]:
        return self.to_response_data()

    def to_response_data(self) -> dict[str, object]:
        """Return the stable CLI response payload."""

        data = {
            "scenario_id": self.scenario_id,
            "outcome": self.outcome.value,
            "created": self.created,
        }
        if self.solution_delta is not None:
            data["solution_delta"] = self.solution_delta.to_response_data()
        return data
