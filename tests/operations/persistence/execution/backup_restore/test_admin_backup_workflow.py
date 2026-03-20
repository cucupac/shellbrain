"""Persistence contracts for first-class admin backup helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import gzip
import json
from pathlib import Path

import pytest

from app.periphery.admin.backup import BackupManifest, create_backup, list_backups, restore_backup, verify_backup
from app.periphery.admin.instance_guard import InstanceMetadataRecord


def test_admin_backup_create_should_write_manifest_and_optional_mirror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin backup create should always write a verifiable artifact and manifest."""

    backup_root = tmp_path / "backups"
    mirror_root = tmp_path / "mirror"
    admin_dsn = "postgresql+psycopg://shellbrain_admin:shellbrain_admin@localhost:5432/shellbrain_live"

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/pg_dump" if name == "pg_dump" else None)
    monkeypatch.setattr(
        "app.periphery.admin.backup.fetch_instance_metadata",
        lambda dsn: InstanceMetadataRecord(
            instance_id="inst-live",
            instance_mode="live",
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="tests",
            notes=None,
        ),
    )
    monkeypatch.setattr("app.periphery.admin.backup._fetch_schema_revision", lambda dsn: "20260320_0008")
    monkeypatch.setattr(
        "app.periphery.admin.backup.fingerprint_summary",
        lambda dsn: {
            "fingerprint": "fp-live",
            "host": "localhost",
            "port": "5432",
            "database": "shellbrain_live",
            "user": "shellbrain_admin",
        },
    )
    monkeypatch.setattr(
        "app.periphery.admin.backup.subprocess.Popen",
        lambda *args, **kwargs: _FakePopen(stdout=b"CREATE TABLE sentinel();\n", stderr=b"", returncode=0),
    )

    manifest = create_backup(admin_dsn=admin_dsn, backup_root=backup_root, mirror_root=mirror_root)
    listed = list_backups(backup_root=backup_root)
    verified = verify_backup(backup_root=backup_root, backup_id=manifest.backup_id)

    artifact_path = backup_root / manifest.instance_id / manifest.artifact_filename
    manifest_path = backup_root / manifest.instance_id / artifact_path.name.replace(".sql.gz", ".manifest.json")

    assert isinstance(manifest, BackupManifest)
    assert listed[0].backup_id == manifest.backup_id
    assert verified.backup_id == manifest.backup_id
    assert artifact_path.exists()
    assert manifest_path.exists()
    assert (mirror_root / manifest.instance_id / artifact_path.name).exists()
    assert (mirror_root / manifest.instance_id / manifest_path.name).exists()


def test_admin_backup_verify_should_detect_hash_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin backup verify should fail when the artifact content no longer matches the manifest hash."""

    backup_root = tmp_path / "backups"
    admin_dsn = "postgresql+psycopg://shellbrain_admin:shellbrain_admin@localhost:5432/shellbrain_live"

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/pg_dump" if name == "pg_dump" else None)
    monkeypatch.setattr(
        "app.periphery.admin.backup.fetch_instance_metadata",
        lambda dsn: InstanceMetadataRecord(
            instance_id="inst-live",
            instance_mode="live",
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="tests",
            notes=None,
        ),
    )
    monkeypatch.setattr("app.periphery.admin.backup._fetch_schema_revision", lambda dsn: "20260320_0008")
    monkeypatch.setattr(
        "app.periphery.admin.backup.fingerprint_summary",
        lambda dsn: {
            "fingerprint": "fp-live",
            "host": "localhost",
            "port": "5432",
            "database": "shellbrain_live",
            "user": "shellbrain_admin",
        },
    )
    monkeypatch.setattr(
        "app.periphery.admin.backup.subprocess.Popen",
        lambda *args, **kwargs: _FakePopen(stdout=b"SELECT 1;\n", stderr=b"", returncode=0),
    )

    manifest = create_backup(admin_dsn=admin_dsn, backup_root=backup_root)
    artifact_path = backup_root / manifest.instance_id / manifest.artifact_filename
    artifact_path.write_bytes(b"tampered")

    with pytest.raises(RuntimeError, match="hash mismatch"):
        verify_backup(backup_root=backup_root, backup_id=manifest.backup_id)


def test_admin_backup_create_should_preserve_path_when_setting_pgpassword(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """managed-container backup env should preserve PATH while injecting PGPASSWORD."""

    backup_root = tmp_path / "backups"
    admin_dsn = "postgresql+psycopg://shellbrain_admin:shellbrain_admin@localhost:5432/shellbrain_live"
    captured: dict[str, object] = {}

    monkeypatch.setenv("PATH", "/usr/local/bin:/usr/bin")
    monkeypatch.setattr(
        "app.periphery.admin.backup.fetch_instance_metadata",
        lambda dsn: InstanceMetadataRecord(
            instance_id="inst-live",
            instance_mode="live",
            created_at=datetime.now(timezone.utc).isoformat(),
            created_by="tests",
            notes=None,
        ),
    )
    monkeypatch.setattr("app.periphery.admin.backup._fetch_schema_revision", lambda dsn: "20260320_0008")
    monkeypatch.setattr(
        "app.periphery.admin.backup.fingerprint_summary",
        lambda dsn: {
            "fingerprint": "fp-live",
            "host": "localhost",
            "port": "5432",
            "database": "shellbrain_live",
            "user": "shellbrain_admin",
        },
    )

    def _fake_popen(*args, **kwargs):
        captured["env"] = kwargs.get("env")
        return _FakePopen(stdout=b"SELECT 1;\n", stderr=b"", returncode=0)

    monkeypatch.setattr("app.periphery.admin.backup.subprocess.Popen", _fake_popen)

    create_backup(
        admin_dsn=admin_dsn,
        backup_root=backup_root,
        container_name="shellbrain-postgres-test",
        container_db_name="shellbrain",
        container_admin_user="shellbrain_admin",
        container_admin_password="secret-password",
    )

    env = captured["env"]
    assert isinstance(env, dict)
    assert env["PGPASSWORD"] == "secret-password"
    assert env["PATH"] == "/usr/local/bin:/usr/bin"


def test_admin_backup_restore_should_refuse_protected_target_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """admin backup restore should never allow in-place restores into protected DB names."""

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/psql" if name == "psql" else None)

    with pytest.raises(RuntimeError, match="protected database name"):
        restore_backup(
            admin_dsn="postgresql+psycopg://shellbrain_admin:shellbrain_admin@localhost:5432/shellbrain_live",
            backup_root=tmp_path,
            target_db="shellbrain",
        )


def test_admin_backup_restore_should_strip_unsupported_transaction_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin backup restore should sanitize unsupported pg_dump session settings before psql."""

    backup_root = tmp_path / "backups"
    instance_dir = backup_root / "inst-live"
    instance_dir.mkdir(parents=True)
    manifest = {
        "backup_id": "b-restore",
        "instance_id": "inst-live",
        "instance_mode": "live",
        "source": {"database": "shellbrain_live", "fingerprint": "fp-live", "host": "localhost", "port": "5432", "user": "shellbrain_admin"},
        "schema_revision": "20260320_0008",
        "created_at": "2026-03-19T00:00:00+00:00",
        "artifact_filename": "restore.sql.gz",
        "artifact_sha256": "ignored",
        "artifact_size_bytes": 0,
        "compression": "gzip",
    }
    (instance_dir / "restore.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with gzip.open(instance_dir / "restore.sql.gz", "wb") as handle:
        handle.write(
            b"SET statement_timeout = 0;\n"
            b"SET transaction_timeout = 0;\n"
            b"SELECT pg_catalog.set_config('search_path', '', false);\n"
            b"CREATE TABLE sentinel(id int);\n"
        )

    captured: dict[str, object] = {}

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/psql" if name == "psql" else None)
    monkeypatch.setattr("app.periphery.admin.backup.verify_backup", lambda **kwargs: BackupManifest(**manifest))
    monkeypatch.setattr("app.periphery.admin.backup._create_empty_database", lambda **kwargs: None)
    monkeypatch.setattr("app.periphery.admin.instance_guard.ensure_instance_metadata", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.periphery.admin.privileges.reconcile_app_role_privileges",
        lambda **kwargs: captured.setdefault("reconciled", kwargs),
    )

    def _fake_run(args, input, capture_output, check):
        captured["input"] = input
        return type("_Completed", (), {"returncode": 0, "stderr": b""})()

    monkeypatch.setattr("app.periphery.admin.backup.subprocess.run", _fake_run)

    restored = restore_backup(
        admin_dsn="postgresql+psycopg://shellbrain_admin:shellbrain_admin@localhost:5432/shellbrain_live",
        backup_root=backup_root,
        target_db="shellbrain_restore_scratch",
        app_dsn="postgresql+psycopg://shellbrain_app:shellbrain@localhost:5432/shellbrain_live",
        backup_id="b-restore",
    )

    restored_sql = captured["input"]
    assert isinstance(restored_sql, bytes)
    assert b"SET statement_timeout = 0;" in restored_sql
    assert b"SET transaction_timeout = 0;" not in restored_sql
    assert b"CREATE TABLE sentinel" in restored_sql
    assert captured["reconciled"] == {
        "admin_dsn": "postgresql+psycopg://shellbrain_admin:shellbrain_admin@localhost:5432/shellbrain_restore_scratch",
        "app_dsn": "postgresql+psycopg://shellbrain_app:shellbrain@localhost:5432/shellbrain_restore_scratch",
    }
    assert restored.backup_id == "b-restore"


class _FakePopen:
    """Minimal subprocess.Popen test double for pg_dump."""

    def __init__(self, *, stdout: bytes, stderr: bytes, returncode: int) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    def __enter__(self) -> _FakePopen:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        _ = (exc_type, exc, tb)

    def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr
