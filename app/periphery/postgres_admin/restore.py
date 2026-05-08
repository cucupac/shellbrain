"""Restore helpers for Shellbrain logical backups."""

from pathlib import Path

from app.core.entities.backups import BackupManifest
from app.periphery.postgres_admin.logical_backup import restore_backup as _restore_backup


def restore_backup(
    *,
    admin_dsn: str,
    backup_root: Path,
    target_db: str,
    app_dsn: str | None = None,
    backup_id: str | None = None,
    container_name: str | None = None,
    container_admin_user: str | None = None,
    container_admin_password: str | None = None,
) -> BackupManifest:
    """Restore one backup into a fresh scratch database."""

    return _restore_backup(
        admin_dsn=admin_dsn,
        backup_root=backup_root,
        target_db=target_db,
        app_dsn=app_dsn,
        backup_id=backup_id,
        container_name=container_name,
        container_admin_user=container_admin_user,
        container_admin_password=container_admin_password,
    )
