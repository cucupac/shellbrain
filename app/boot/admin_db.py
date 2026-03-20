"""Boot helpers for privileged admin database actions and safety settings."""

from __future__ import annotations

import os
from pathlib import Path

from app.boot.config import get_config_provider
from app.boot.home import get_machine_backups_dir
from app.periphery.admin.machine_state import try_load_machine_config


def get_admin_db_dsn() -> str:
    """Resolve the privileged admin DSN from environment-backed runtime config."""

    machine_config, machine_error = try_load_machine_config()
    if machine_error:
        raise RuntimeError(
            "Shellbrain machine config is unreadable. Rerun `shellbrain init` to repair it."
        )
    if machine_config is not None:
        return machine_config.database.admin_dsn

    runtime = get_config_provider().get_runtime()
    database = runtime.get("database")
    if not isinstance(database, dict):
        raise RuntimeError("runtime.database must be configured")
    admin_dsn_env = database.get("admin_dsn_env")
    if not isinstance(admin_dsn_env, str) or not admin_dsn_env:
        raise RuntimeError("runtime.database.admin_dsn_env must be configured")
    dsn = os.getenv(admin_dsn_env)
    if not dsn:
        raise RuntimeError(f"{admin_dsn_env} is not set")
    return dsn


def get_optional_admin_db_dsn() -> str | None:
    """Resolve the privileged admin DSN when present, otherwise return None."""

    machine_config, machine_error = try_load_machine_config()
    if machine_error:
        return None
    if machine_config is not None:
        return machine_config.database.admin_dsn

    runtime = get_config_provider().get_runtime()
    database = runtime.get("database")
    if not isinstance(database, dict):
        return None
    admin_dsn_env = database.get("admin_dsn_env")
    if not isinstance(admin_dsn_env, str) or not admin_dsn_env:
        return None
    return os.getenv(admin_dsn_env)


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
