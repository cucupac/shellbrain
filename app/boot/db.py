"""This module defines boot-time factory helpers for database engine and sessions."""

from app.boot._dsn_resolution import resolve_database_dsn
from app.boot.config import get_config_provider
from app.periphery.admin.machine_state import try_load_machine_config
from app.periphery.db.engine import get_engine
from app.periphery.db.session import get_session_factory


def get_db_dsn() -> str:
    """This function resolves the database DSN from environment configuration."""

    dsn = _resolve_app_db_dsn(required=True)
    assert dsn is not None
    return dsn


def get_optional_db_dsn() -> str | None:
    """Resolve the application DSN when present, otherwise return None."""

    return _resolve_app_db_dsn(required=False)


def get_engine_instance():
    """This function builds a shared SQLAlchemy engine for the application."""

    return get_engine(get_db_dsn())


def get_session_factory_instance():
    """This function builds a reusable SQLAlchemy session factory for the app."""

    return get_session_factory(get_engine_instance())


def _resolve_app_db_dsn(*, required: bool) -> str | None:
    """Resolve the application DSN from machine config or runtime env config."""

    return resolve_database_dsn(
        load_machine_config=try_load_machine_config,
        runtime_provider=lambda: get_config_provider().get_runtime(),
        machine_field="app_dsn",
        runtime_env_key="dsn_env",
        required=required,
    )
