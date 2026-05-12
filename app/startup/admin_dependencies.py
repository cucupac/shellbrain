"""Dependency bundle for human admin CLI commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AdminCommandDependencies:
    """Startup-provided concrete behavior for admin CLI commands."""

    upgrade_database: Callable[[], None]
    migration_conflict_error: type[Exception]
    get_admin_db_dsn: Callable[[], str]
    get_optional_admin_db_dsn: Callable[[], str | None]
    get_optional_db_dsn: Callable[[], str | None]
    get_engine_instance: Callable[[], Any]
    get_backup_dir: Callable[[], Path]
    get_backup_mirror_dir: Callable[[], Path | None]
    managed_backup_kwargs: Callable[[object, str | None], dict[str, Any]]
    managed_restore_kwargs: Callable[[dict[str, Any]], dict[str, Any]]
    create_backup: Callable[..., Any]
    list_backups: Callable[..., list[Any]]
    verify_backup: Callable[..., Any]
    restore_backup: Callable[..., Any]
    build_doctor_report: Callable[..., Any]
    build_admin_analytics_report: Callable[..., Any]
    backfill_model_usage: Callable[..., Any]
    install_repo_claude_hook: Callable[..., Any]
    install_managed_host_assets: Callable[..., Any]
    load_session_state: Callable[..., Any]
    delete_session_state: Callable[..., Any]
    gc_session_state: Callable[..., Any]
