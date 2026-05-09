"""This module defines an interface for obtaining current time values."""

from abc import ABC, abstractmethod
from datetime import datetime


class IClock(ABC):
    """This interface defines a deterministic clock boundary."""

    @abstractmethod
    def now(self) -> datetime:
        """This method returns the current timestamp."""
