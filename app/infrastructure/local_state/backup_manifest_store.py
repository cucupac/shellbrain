"""Filesystem manifest helpers for logical backup artifacts."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from app.core.entities.backups import BackupManifest


def write_backup_manifest(*, path: Path, manifest: BackupManifest) -> None:
    """Write one backup manifest JSON file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True), encoding="utf-8"
    )


def read_backup_manifest(*, path: Path) -> BackupManifest:
    """Read one backup manifest JSON file."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return BackupManifest(**payload)


def list_backup_manifests(*, backup_root: Path) -> list[BackupManifest]:
    """Return every parseable manifest under one backup root."""

    if not backup_root.exists():
        return []
    manifests: list[BackupManifest] = []
    for path in sorted(backup_root.rglob("*.manifest.json")):
        try:
            manifests.append(read_backup_manifest(path=path))
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            continue
    return sorted(manifests, key=lambda item: item.created_at, reverse=True)
