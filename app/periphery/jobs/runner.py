"""This module defines an in-process job runner used by boot-time wiring."""

from typing import Any, Callable

from app.core.interfaces.jobs import IJobRunner


class InProcessJobRunner(IJobRunner):
    """This class executes registered jobs synchronously in the current process."""

    def __init__(self, registry: dict[str, Callable[[dict[str, Any]], None]]) -> None:
        """This method stores job callables keyed by job name."""

        self._registry = dict[str, Callable[[dict[str, Any]], None]](registry)

    def run(self, *, job_name: str, payload: dict[str, Any]) -> None:
        """This method executes a registered job callable with the given payload."""

        job = self._registry.get(job_name)
        if job is None:
            raise KeyError(f"Unknown job: {job_name}")
        job(payload)
