"""Shared helpers for resolving configured application and admin DSNs."""

from __future__ import annotations

import os
from typing import Callable


def resolve_database_dsn(
    *,
    load_machine_config: Callable[[], tuple[object | None, str | None]],
    machine_field: str,
    env_name: str,
    required: bool,
) -> str | None:
    """Resolve one configured DSN from machine config first, then runtime env config."""

    machine_config, machine_error = load_machine_config()
    if machine_error:
        if required:
            raise RuntimeError(
                "Shellbrain machine config is unreadable. Rerun `shellbrain init` to repair it."
            )
        return None
    if machine_config is not None:
        return getattr(machine_config.database, machine_field)

    dsn = os.getenv(env_name)
    if not dsn and required:
        raise RuntimeError(f"{env_name} is not set")
    return dsn or None
