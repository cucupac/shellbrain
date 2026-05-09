"""Composition wrappers for backup admin commands."""

from __future__ import annotations

from pathlib import Path

from app.core.entities.backups import BackupManifest, BackupTarget
from app.core.use_cases.admin.create_backup import (
    create_backup as create_backup_use_case,
)
from app.core.use_cases.admin.restore_backup import (
    restore_backup as restore_backup_use_case,
)
from app.core.use_cases.admin.verify_backup import (
    verify_backup as verify_backup_use_case,
)
from app.infrastructure.db.admin import logical_backup


def create_backup(**kwargs) -> BackupManifest:
    """Create a logical backup through core policy and infrastructure mechanics."""

    return create_backup_use_case(
        create_logical_backup=logical_backup.create_backup, **kwargs
    )


def list_backups(*, backup_root: Path) -> list[BackupManifest]:
    """List available logical backups from the manifest store."""

    return logical_backup.list_backups(backup_root=backup_root)


def verify_backup(**kwargs) -> BackupManifest:
    """Verify a backup and return its manifest for CLI compatibility."""

    result = verify_backup_use_case(
        verify_logical_backup=logical_backup.verify_backup, **kwargs
    )
    return logical_backup.resolve_backup(
        backup_root=kwargs["backup_root"], backup_id=result.backup_id
    )


def restore_backup(*, target_db: str, **kwargs) -> BackupManifest:
    """Restore a backup through core safety policy and infrastructure mechanics."""

    return restore_backup_use_case(
        target=BackupTarget(database_name=target_db),
        restore_logical_backup=logical_backup.restore_backup,
        **kwargs,
    )
