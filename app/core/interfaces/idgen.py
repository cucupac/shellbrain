"""This module defines an interface for generating stable identifiers."""

from abc import ABC, abstractmethod


class IIdGenerator(ABC):
    """This interface defines generation of unique string identifiers."""

    @abstractmethod
    def new_id(self) -> str:
        """This method returns a new unique identifier string."""
