"""Composition helpers for human admin CLI endpoints."""

from __future__ import annotations

from app.infrastructure.local_state import machine_config_store


def managed_backup_kwargs() -> dict[str, object]:
    """Return managed-container backup kwargs when machine config is active and readable."""

    machine_config, machine_error = machine_config_store.try_load_machine_config()
    if (
        machine_error is not None
        or machine_config is None
        or machine_config.runtime_mode != "managed_local"
        or machine_config.managed is None
    ):
        return {}
    return {
        "container_name": machine_config.managed.container_name,
        "container_db_name": machine_config.managed.db_name,
        "container_admin_user": machine_config.managed.admin_user,
        "container_admin_password": machine_config.managed.admin_password,
    }


def managed_restore_kwargs(backup_kwargs: dict[str, object]) -> dict[str, object]:
    """Trim backup kwargs down to the subset restore understands."""

    return {
        key: value
        for key, value in backup_kwargs.items()
        if key in {"container_name", "container_admin_user", "container_admin_password"}
    }
