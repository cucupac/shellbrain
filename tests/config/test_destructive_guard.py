"""Contracts for the shared backup-before-destructive admin guard."""

from __future__ import annotations

from pathlib import Path

from app.periphery.admin.backup import BackupManifest
from app.periphery.admin.destructive_guard import backup_and_verify_before_destructive_action


def test_destructive_guard_should_create_and_verify_backup(monkeypatch, tmp_path: Path) -> None:
    """The shared destructive guard should always create and verify one backup."""

    calls: list[tuple[str, object]] = []
    manifest = BackupManifest(
        backup_id="backup-1",
        instance_id="inst-1",
        instance_mode="live",
        source={"fingerprint": "abc", "host": "localhost", "port": "5432", "database": "shellbrain", "user": "admin"},
        schema_revision="20260320_0008",
        created_at="2026-03-19T00:00:00+00:00",
        artifact_filename="artifact.sql.gz",
        artifact_sha256="deadbeef",
        artifact_size_bytes=123,
        compression="gzip",
    )

    def _fake_create_backup(**kwargs):
        calls.append(("create", kwargs))
        return manifest

    def _fake_verify_backup(**kwargs):
        calls.append(("verify", kwargs))
        return manifest

    monkeypatch.setattr("app.periphery.admin.destructive_guard.create_backup", _fake_create_backup)
    monkeypatch.setattr("app.periphery.admin.destructive_guard.verify_backup", _fake_verify_backup)

    result = backup_and_verify_before_destructive_action(
        admin_dsn="postgresql+psycopg://admin:pw@localhost:5432/shellbrain",
        backup_root=tmp_path / "backups",
        mirror_root=tmp_path / "mirror",
        container_name="shellbrain-postgres",
        container_db_name="shellbrain",
        container_admin_user="shellbrain_admin",
        container_admin_password="secret",
    )

    assert result == manifest
    assert calls == [
        (
            "create",
            {
                "admin_dsn": "postgresql+psycopg://admin:pw@localhost:5432/shellbrain",
                "backup_root": tmp_path / "backups",
                "mirror_root": tmp_path / "mirror",
                "container_name": "shellbrain-postgres",
                "container_db_name": "shellbrain",
                "container_admin_user": "shellbrain_admin",
                "container_admin_password": "secret",
            },
        ),
        (
            "verify",
            {
                "backup_root": tmp_path / "backups",
                "backup_id": "backup-1",
            },
        ),
    ]
