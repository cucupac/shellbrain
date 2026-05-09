"""Core backup creation policy."""

from __future__ import annotations

from collections.abc import Callable

from app.core.entities.backups import BackupManifest


def create_backup(
    *, create_logical_backup: Callable[..., BackupManifest], **kwargs
) -> BackupManifest:
    """Create a backup through the injected logical-backup adapter."""

    manifest = create_logical_backup(**kwargs)
    if not manifest.backup_id:
        raise RuntimeError("Backup adapter returned a manifest without a backup id.")
    return manifest
