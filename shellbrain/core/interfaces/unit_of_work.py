"""This module defines the unit-of-work interface used to enforce transaction boundaries."""

from abc import ABC, abstractmethod
from typing import Self

from shellbrain.core.interfaces.repos import (
    IAssociationsRepo,
    IEpisodesRepo,
    IEvidenceRepo,
    IExperiencesRepo,
    IKeywordRetrievalRepo,
    IMemoriesRepo,
    IReadPolicyRepo,
    ISemanticRetrievalRepo,
    IUtilityRepo,
)
from shellbrain.core.interfaces.retrieval import IVectorSearch


class IUnitOfWork(ABC):
    """This interface defines transactional access to all repositories."""

    memories: IMemoriesRepo
    experiences: IExperiencesRepo
    associations: IAssociationsRepo
    utility: IUtilityRepo
    episodes: IEpisodesRepo
    evidence: IEvidenceRepo
    semantic_retrieval: ISemanticRetrievalRepo
    keyword_retrieval: IKeywordRetrievalRepo
    read_policy: IReadPolicyRepo
    vector_search: IVectorSearch | None

    @abstractmethod
    def __enter__(self) -> Self:
        """This method opens a transaction scope and returns itself."""

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """This method exits the transaction scope with commit-or-rollback behavior."""

    @abstractmethod
    def commit(self) -> None:
        """This method commits the current transaction."""

    @abstractmethod
    def rollback(self) -> None:
        """This method rolls back the current transaction."""
