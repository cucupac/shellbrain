"""Dependency bundle for human admin CLI commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AdminCommandDependencies:
    """Startup-provided concrete behavior for admin CLI commands."""

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
