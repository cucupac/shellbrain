"""Core restore safety policy."""

from __future__ import annotations

from collections.abc import Callable

from app.core.entities.backups import BackupManifest, BackupPolicyError, BackupTarget


_PROTECTED_DATABASE_NAMES = {"postgres", "template0", "template1", "shellbrain"}


def restore_backup(
    *,
    target: BackupTarget,
    restore_logical_backup: Callable[..., BackupManifest],
    **kwargs,
) -> BackupManifest:
    """Validate restore safety policy before invoking concrete restore mechanics."""

    target_db = target.database_name.strip()
    if not target_db:
        raise BackupPolicyError("Restore target database name is required.")
    if target_db.lower() in _PROTECTED_DATABASE_NAMES:
        raise BackupPolicyError(
            f"Refusing to restore into protected database name '{target_db}'. Use a fresh scratch database name."
        )
    if not target_db.lower().startswith("shellbrain_restore"):
        raise BackupPolicyError(
            "Restore target must be a scratch database named shellbrain_restore*."
        )
    return restore_logical_backup(target_db=target_db, **kwargs)
