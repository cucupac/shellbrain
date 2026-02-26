"""This module defines boot-time helpers that register and return job runner instances."""

from app.core.use_cases.association_consolidation import run_association_consolidation
from app.core.use_cases.scenario_projection import run_scenario_projection
from app.periphery.jobs.runner import InProcessJobRunner


def get_job_runner() -> InProcessJobRunner:
    """This function builds an in-process runner with registered default jobs."""

    return InProcessJobRunner(
        {
            "association_consolidation": run_association_consolidation,
            "scenario_projection": run_scenario_projection,
        }
    )
