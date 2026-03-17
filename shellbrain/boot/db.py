"""This module defines boot-time factory helpers for database engine and sessions."""

import os
from pathlib import Path

from shellbrain.boot.config import get_config_provider
from shellbrain.periphery.db.engine import get_engine
from shellbrain.periphery.db.session import get_session_factory


def get_db_dsn() -> str:
    """This function resolves the database DSN from environment configuration."""

    runtime = get_config_provider().get_runtime()
    database = runtime.get("database")
    if not isinstance(database, dict):
        raise RuntimeError("runtime.database must be configured")
    dsn_env = database.get("dsn_env")
    if not isinstance(dsn_env, str) or not dsn_env:
        raise RuntimeError("runtime.database.dsn_env must be configured")
    dsn = os.getenv(dsn_env)
    if not dsn:
        raise RuntimeError(f"{dsn_env} is not set")
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
