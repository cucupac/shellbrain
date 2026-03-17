"""This module defines lower-level retrieval interfaces for embedding and lexical operations."""

from abc import ABC, abstractmethod
from typing import Sequence


class IVectorSearch(ABC):
    """This interface defines vector embedding and similarity lookup capabilities."""

    @abstractmethod
    def embed_query(self, text: str) -> Sequence[float]:
        """This method returns an embedding vector for query text."""


class IKeywordSearch(ABC):
    """This interface defines lexical lookup capabilities for query text."""

    @abstractmethod
    def normalize_query(self, text: str) -> str:
        """This method normalizes text before lexical retrieval."""
