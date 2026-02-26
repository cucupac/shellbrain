"""This module defines a boundary for generating embedding vectors from text."""

from abc import ABC, abstractmethod
from typing import Sequence


class IEmbeddingProvider(ABC):
    """This interface defines embedding generation for create-time memory writes."""

    @abstractmethod
    def embed(self, text: str) -> Sequence[float]:
        """This method returns an embedding vector for the given text."""
