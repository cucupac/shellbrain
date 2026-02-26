"""This module defines boot-time helpers that expose repository-ready unit-of-work factories."""

from app.boot.db import get_session_factory_instance
from app.periphery.db.uow import PostgresUnitOfWork


def get_uow() -> PostgresUnitOfWork:
    """This function creates a fresh unit-of-work instance with bound repositories."""

    return PostgresUnitOfWork(get_session_factory_instance())
