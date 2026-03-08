"""This module defines a PostgreSQL-backed unit-of-work implementation with repo bindings."""

from collections.abc import Callable

from app.core.interfaces.retrieval import IVectorSearch
from app.core.interfaces.unit_of_work import IUnitOfWork
from app.periphery.db.repos.relational.associations_repo import AssociationsRepo
from app.periphery.db.repos.relational.episodes_repo import EpisodesRepo
from app.periphery.db.repos.relational.evidence_repo import EvidenceRepo
from app.periphery.db.repos.relational.experiences_repo import ExperiencesRepo
from app.periphery.db.repos.relational.memories_repo import MemoriesRepo
from app.periphery.db.repos.relational.read_policy_repo import ReadPolicyRepo
from app.periphery.db.repos.relational.utility_repo import UtilityRepo
from app.periphery.db.repos.semantic.keyword_retrieval_repo import KeywordRetrievalRepo
from app.periphery.db.repos.semantic.semantic_retrieval_repo import SemanticRetrievalRepo


class PostgresUnitOfWork(IUnitOfWork):
    """This class coordinates transaction boundaries and repository lifecycle."""

    def __init__(
        self,
        session_factory,
        *,
        vector_search_factory: Callable[[], IVectorSearch] | None = None,
    ) -> None:
        """Store factories used to create one transaction scope and its read dependencies."""

        self._session_factory = session_factory
        self._vector_search_factory = vector_search_factory
        self._session = None
        self.vector_search = None

    def __enter__(self):
        """This method opens a DB session and binds repositories to it."""

        self._session = self._session_factory()
        self.vector_search = (
            self._vector_search_factory() if self._vector_search_factory is not None else None
        )
        self.memories = MemoriesRepo(self._session)
        self.experiences = ExperiencesRepo(self._session)
        self.associations = AssociationsRepo(self._session)
        self.utility = UtilityRepo(self._session)
        self.episodes = EpisodesRepo(self._session)
        self.evidence = EvidenceRepo(self._session)
        self.semantic_retrieval = SemanticRetrievalRepo(self._session)
        self.keyword_retrieval = KeywordRetrievalRepo(self._session)
        self.read_policy = ReadPolicyRepo(self._session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """This method commits on success and rolls back on failure before closing session."""

        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        if self._session is not None:
            self._session.close()
        self.vector_search = None

    def commit(self) -> None:
        """This method commits the active SQLAlchemy session."""

        if self._session is not None:
            self._session.commit()

    def rollback(self) -> None:
        """This method rolls back the active SQLAlchemy session."""

        if self._session is not None:
            self._session.rollback()
