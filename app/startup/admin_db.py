"""Boot helpers for privileged admin database actions and safety settings."""

from __future__ import annotations

import os
from pathlib import Path

from app.startup.dsn_resolution import resolve_database_dsn
from app.startup.config import get_config_provider
from app.periphery.local_state.paths import get_machine_backups_dir
from app.periphery.local_state.machine_config_store import try_load_machine_config


def get_admin_db_dsn() -> str:
    """Resolve the privileged admin DSN from environment-backed runtime config."""

    dsn = _resolve_admin_db_dsn(required=True)
    assert dsn is not None
    return dsn


def get_optional_admin_db_dsn() -> str | None:
    """Resolve the privileged admin DSN when present, otherwise return None."""

    return _resolve_admin_db_dsn(required=False)


def get_backup_dir() -> Path:
    """Resolve the on-disk backup directory, defaulting outside the repo tree."""

    machine_config, machine_error = try_load_machine_config()
    if machine_error:
        return get_machine_backups_dir()
    if machine_config is not None:
        return Path(machine_config.backups.root).expanduser().resolve()
    return Path(os.getenv("SHELLBRAIN_BACKUP_DIR", str(get_machine_backups_dir()))).expanduser().resolve()


def get_backup_mirror_dir() -> Path | None:
    """Resolve the optional mirrored backup directory."""

    configured = os.getenv("SHELLBRAIN_BACKUP_MIRROR_DIR")
    if not configured:
        return None
    return Path(configured).expanduser().resolve()


def should_fail_on_unsafe_app_role() -> bool:
    """Return whether app commands should fail instead of warning on unsafe DB roles."""

    configured = os.getenv("SHELLBRAIN_FAIL_ON_UNSAFE_DB_ROLE")
    if configured is None or not configured.strip():
        return True
    return configured.strip().lower() not in {"0", "false", "no", "off"}


def get_instance_mode_default() -> str:
    """Resolve the default instance mode used when stamping metadata for the current DB."""

    return os.getenv("SHELLBRAIN_INSTANCE_MODE", "live").strip().lower() or "live"


def _resolve_admin_db_dsn(*, required: bool) -> str | None:
    """Resolve the admin DSN from machine config or runtime env config."""

    return resolve_database_dsn(
        load_machine_config=try_load_machine_config,
        runtime_provider=lambda: get_config_provider().get_runtime(),
        machine_field="admin_dsn",
        runtime_env_key="admin_dsn_env",
        required=required,
    )
