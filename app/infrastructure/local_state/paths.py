"""Helpers for locating Shellbrain machine-owned runtime directories."""

from __future__ import annotations

import os
from pathlib import Path


def get_shellbrain_home() -> Path:
    """Return the machine-owned Shellbrain home root."""

    configured = os.getenv("SHELLBRAIN_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path("~/.shellbrain").expanduser().resolve()


def get_machine_config_path() -> Path:
    """Return the machine configuration file path."""

    return get_shellbrain_home() / "config.toml"


def get_machine_lock_path() -> Path:
    """Return the machine-scoped init lock path."""

    return get_shellbrain_home() / "init.lock"


def get_machine_models_dir() -> Path:
    """Return the machine-owned embedding model cache path."""

    return get_shellbrain_home() / "models"


def get_machine_backups_dir() -> Path:
    """Return the machine-owned default backup directory."""

    return get_shellbrain_home() / "backups"


def get_machine_postgres_data_dir() -> Path:
    """Return the managed Postgres bind-mounted data directory."""

    return get_shellbrain_home() / "postgres-data"
