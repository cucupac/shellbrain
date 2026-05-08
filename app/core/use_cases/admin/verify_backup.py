"""Core backup verification policy."""

from __future__ import annotations

from collections.abc import Callable

from app.core.entities.backups import BackupManifest, BackupVerificationResult


def verify_backup(*, verify_logical_backup: Callable[..., BackupManifest], **kwargs) -> BackupVerificationResult:
    """Verify a backup artifact through the injected adapter and return a stable result."""

    manifest = verify_logical_backup(**kwargs)
    return BackupVerificationResult(
        backup_id=manifest.backup_id,
        artifact_sha256=manifest.artifact_sha256,
        artifact_size_bytes=manifest.artifact_size_bytes,
        verified=True,
    )
