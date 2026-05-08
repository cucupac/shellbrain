"""This module defines PostgreSQL engine construction helpers for application boot wiring."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_engine(dsn: str) -> Engine:
    """This function creates a SQLAlchemy engine for the provided PostgreSQL DSN."""

    return create_engine(dsn, future=True)
