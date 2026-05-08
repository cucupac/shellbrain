"""Core backup entities and policy errors."""

from __future__ import annotations

from dataclasses import dataclass


BackupId = str


@dataclass(frozen=True)
class BackupTarget:
    """Requested restore target database."""

    database_name: str


@dataclass(frozen=True)
class BackupManifest:
    """Portable metadata stored next to one logical backup artifact."""

    backup_id: BackupId
    instance_id: str
    instance_mode: str
    source: dict[str, str]
    schema_revision: str
    created_at: str
    artifact_filename: str
    artifact_sha256: str
    artifact_size_bytes: int
    compression: str


@dataclass(frozen=True)
class BackupVerificationResult:
    """Stable result for a verified backup artifact."""

    backup_id: BackupId
    artifact_sha256: str
    artifact_size_bytes: int
    verified: bool


class BackupPolicyError(RuntimeError):
    """Raised when a backup or restore request violates core safety policy."""
