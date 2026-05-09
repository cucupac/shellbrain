"""Startup wiring for packaged database migrations."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.local_state.machine_config_store import MachineConfig
from app.infrastructure.postgres_admin.migrations import (
    DatabaseRevisionAheadOfInstalledPackageError,
    apply_packaged_migrations,
)
from app.startup.admin_db import (
    get_admin_db_dsn,
    get_backup_dir,
    get_backup_mirror_dir,
    get_instance_mode_default,
)
from app.startup.db import get_optional_db_dsn


class DatabaseMigrationConflictError(RuntimeError):
    """Raised when startup cannot safely apply packaged migrations."""


def upgrade_database(revision: str = "head") -> None:
    """Apply packaged migrations using configured startup settings."""

    try:
        apply_packaged_migrations(
            admin_dsn=get_admin_db_dsn(),
            app_dsn=get_optional_db_dsn(),
            backup_root=get_backup_dir(),
            mirror_root=get_backup_mirror_dir(),
            instance_mode=get_instance_mode_default(),
            revision=revision,
        )
    except DatabaseRevisionAheadOfInstalledPackageError as exc:
        raise DatabaseMigrationConflictError(str(exc)) from exc


def upgrade_database_for_config(config: MachineConfig, revision: str = "head") -> bool:
    """Apply packaged migrations against an init-managed runtime config."""

    mirror_root = (
        None if config.backups.mirror_root is None else Path(config.backups.mirror_root)
    )
    try:
        return apply_packaged_migrations(
            admin_dsn=config.database.admin_dsn,
            app_dsn=config.database.app_dsn,
            backup_root=Path(config.backups.root),
            mirror_root=mirror_root,
            instance_mode=get_instance_mode_default(),
            revision=revision,
        )
    except DatabaseRevisionAheadOfInstalledPackageError as exc:
        raise DatabaseMigrationConflictError(str(exc)) from exc
