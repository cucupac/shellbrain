"""This module defines boot-time helpers used by CLI handlers to obtain use-case dependencies."""

from app.boot.repos import get_uow


def get_uow_factory():
    """This function returns a callable that creates fresh unit-of-work instances."""

    return get_uow
