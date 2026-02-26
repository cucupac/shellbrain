"""This module defines boot-time helpers used by CLI handlers to obtain use-case dependencies."""

from app.boot.embeddings import get_embedding_model_name, get_embedding_provider
from app.boot.repos import get_uow


def get_uow_factory():
    """This function returns a callable that creates fresh unit-of-work instances."""

    return get_uow


def get_embedding_provider_factory():
    """This function returns a callable that creates fresh embedding providers."""

    return get_embedding_provider


def get_embedding_model():
    """This function returns the model label that should be stored for embedding rows."""

    return get_embedding_model_name()
