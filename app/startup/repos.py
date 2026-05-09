"""This module defines boot-time helpers that expose repository-ready unit-of-work factories."""

from app.startup.db import get_session_factory_instance
from app.startup.embeddings import get_embedding_provider
from app.infrastructure.db.uow import PostgresUnitOfWork
from app.infrastructure.embeddings.query_vector_search import (
    EmbeddingBackedVectorSearch,
)


def get_uow() -> PostgresUnitOfWork:
    """This function creates a fresh unit-of-work instance with bound repositories."""

    return PostgresUnitOfWork(
        get_session_factory_instance(),
        vector_search_factory=lambda: EmbeddingBackedVectorSearch(
            get_embedding_provider()
        ),
    )
