"""This module defines boot-time factory helpers for database engine and sessions."""

from functools import lru_cache

from app.startup.config import get_config_provider
from app.startup.dsn_resolution import resolve_database_dsn
from app.infrastructure.local_state.machine_config_store import try_load_machine_config
from app.infrastructure.db.runtime.engine import get_engine
from app.infrastructure.db.runtime.session import get_session_factory


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

    return _get_engine_instance_for_dsn(get_db_dsn())


def get_session_factory_instance():
    """This function builds a reusable SQLAlchemy session factory for the app."""

    return _get_session_factory_for_dsn(get_db_dsn())


def clear_db_runtime_caches() -> None:
    """Clear process-local DB factories.

    Tests and rare runtime reconfiguration paths can call this after changing DSNs.
    """

    _get_engine_instance_for_dsn.cache_clear()
    _get_session_factory_for_dsn.cache_clear()


@lru_cache(maxsize=4)
def _get_engine_instance_for_dsn(dsn: str):
    """Build one process-local engine per DSN."""

    return get_engine(dsn)


@lru_cache(maxsize=4)
def _get_session_factory_for_dsn(dsn: str):
    """Build one process-local session factory per DSN."""

    return get_session_factory(_get_engine_instance_for_dsn(dsn))


def _resolve_app_db_dsn(*, required: bool) -> str | None:
    """Resolve the application DSN from machine config or runtime env config."""

    return resolve_database_dsn(
        load_machine_config=try_load_machine_config,
        runtime_provider=lambda: get_config_provider().get_runtime(),
        machine_field="app_dsn",
        runtime_env_key="dsn_env",
        required=required,
    )
