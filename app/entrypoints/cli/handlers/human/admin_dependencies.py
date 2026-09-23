"""Entrypoint-owned dependency protocol for human admin commands."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol


class AdminCommandDependencies(Protocol):
    """Startup-composed behavior consumed by human admin handlers."""

    get_admin_db_dsn: Callable[[], str]
    get_optional_db_dsn: Callable[[], str | None]
    get_backup_dir: Callable[[], Path]
    get_backup_mirror_dir: Callable[[], Path | None]
    managed_backup_kwargs: Callable[[], dict[str, Any]]
    managed_restore_kwargs: Callable[[dict[str, Any]], dict[str, Any]]
    create_backup: Callable[..., Any]
    list_backups: Callable[..., list[Any]]
    verify_backup: Callable[..., Any]
    restore_backup: Callable[..., Any]
    save_recall_provider: Callable[[str], None]
