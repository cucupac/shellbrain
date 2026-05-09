"""Shared guardrails for official destructive Shellbrain admin operations."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.db.admin.backups.logical_backup import (
    BackupManifest,
    create_backup,
    verify_backup,
)


def backup_and_verify_before_destructive_action(
    *,
    admin_dsn: str,
    backup_root: Path,
    mirror_root: Path | None = None,
    container_name: str | None = None,
    container_db_name: str | None = None,
    container_admin_user: str | None = None,
    container_admin_password: str | None = None,
) -> BackupManifest:
    """Create and verify one backup before an official destructive admin mutation."""

    manifest = create_backup(
        admin_dsn=admin_dsn,
        backup_root=backup_root,
        mirror_root=mirror_root,
        container_name=container_name,
        container_db_name=container_db_name,
        container_admin_user=container_admin_user,
        container_admin_password=container_admin_password,
    )
    verify_backup(backup_root=backup_root, backup_id=manifest.backup_id)
    return manifest
