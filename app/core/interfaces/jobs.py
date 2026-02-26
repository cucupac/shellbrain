"""This module defines interfaces for synchronous or asynchronous job execution."""

from abc import ABC, abstractmethod
from typing import Any


class IJobRunner(ABC):
    """This interface defines a boundary for scheduling background-style jobs."""

    @abstractmethod
    def run(self, *, job_name: str, payload: dict[str, Any]) -> None:
        """This method executes a named job with a structured payload."""
