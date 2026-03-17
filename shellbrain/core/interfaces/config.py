"""This module defines configuration provider interfaces for policy and runtime values."""

from abc import ABC, abstractmethod
from typing import Any


class IConfigProvider(ABC):
    """This interface defines accessors for policy and runtime configuration sections."""

    @abstractmethod
    def get_read_policy(self) -> dict[str, Any]:
        """This method returns read-policy configuration values."""

    @abstractmethod
    def get_create_policy(self) -> dict[str, Any]:
        """This method returns create-policy configuration values."""

    @abstractmethod
    def get_update_policy(self) -> dict[str, Any]:
        """This method returns update-policy configuration values."""

    @abstractmethod
    def get_thresholds(self) -> dict[str, Any]:
        """This method returns threshold configuration values."""

    @abstractmethod
    def get_runtime(self) -> dict[str, Any]:
        """This method returns runtime configuration values."""
