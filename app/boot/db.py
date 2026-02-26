"""This module defines boot-time factory helpers for database engine and sessions."""

import os
from pathlib import Path

from app.periphery.db.engine import get_engine
from app.periphery.db.session import get_session_factory


def get_db_dsn() -> str:
    """This function resolves the database DSN from environment configuration."""

    dsn = os.getenv("MEMORY_DB_DSN")
    if not dsn:
        raise RuntimeError("MEMORY_DB_DSN is not set")
    return dsn


def get_engine_instance():
    """This function builds a shared SQLAlchemy engine for the application."""

    return get_engine(get_db_dsn())


def get_session_factory_instance():
    """This function builds a reusable SQLAlchemy session factory for the app."""

    return get_session_factory(get_engine_instance())


def get_defaults_dir() -> Path:
    """This function returns the path to bundled YAML default configuration files."""

    return Path(__file__).resolve().parents[1] / "config" / "defaults"
