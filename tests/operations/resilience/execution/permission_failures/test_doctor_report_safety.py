"""Resilience contracts for safety reporting and privilege diagnostics."""

from __future__ import annotations

from pathlib import Path

from shellbrain.periphery.admin.backup import BackupManifest
from shellbrain.periphery.admin.doctor import build_doctor_report
from shellbrain.periphery.admin.instance_guard import InstanceMetadataRecord


def test_doctor_report_should_tolerate_missing_app_dsn(monkeypatch, tmp_path: Path) -> None:
    """doctor should still produce one report when the app DSN is not configured."""

    monkeypatch.setattr("shellbrain.periphery.admin.doctor.list_backups", lambda backup_root: [])
    monkeypatch.setattr("shellbrain.periphery.admin.doctor.inspect_role_safety", lambda dsn: ["warn"] if dsn else [])
    monkeypatch.setattr(
        "shellbrain.periphery.admin.doctor.fetch_instance_metadata",
        lambda dsn: InstanceMetadataRecord(
            instance_id="inst-live",
            instance_mode="live",
            created_at="2026-03-19T00:00:00+00:00",
            created_by="tests",
            notes=None,
        ),
    )

    report = build_doctor_report(
        app_dsn=None,
        admin_dsn="postgresql+psycopg://shellbrain_admin:shellbrain_admin@localhost:5432/shellbrain_live",
        backup_root=tmp_path,
    )

    assert report["app_dsn_configured"] is False
    assert report["admin_dsn_configured"] is True
    assert report["schema_revision"] is None
    assert report["app_role_warnings"] == []
    assert report["admin_role_warnings"] == ["warn"]
    assert report["config_status"] in {"absent", "ok", "corrupt"}
    assert report["effective_config"]["admin_dsn"] == "postgresql://<redacted>@localhost:5432/shellbrain_live"


def test_doctor_report_should_include_latest_backup_age(monkeypatch, tmp_path: Path) -> None:
    """doctor should summarize backup age and both role-safety channels."""

    monkeypatch.setattr(
        "shellbrain.periphery.admin.doctor.list_backups",
        lambda backup_root: [
            BackupManifest(
                backup_id="b-1",
                instance_id="inst-live",
                instance_mode="live",
                source={"database": "shellbrain_live"},
                schema_revision="20260320_0008",
                created_at="2026-03-19T00:00:00+00:00",
                artifact_filename="artifact.sql.gz",
                artifact_sha256="deadbeef",
                artifact_size_bytes=10,
                compression="gzip",
            )
        ],
    )
    monkeypatch.setattr(
        "shellbrain.periphery.admin.doctor.fetch_instance_metadata",
        lambda dsn: InstanceMetadataRecord(
            instance_id="inst-live",
            instance_mode="live",
            created_at="2026-03-19T00:00:00+00:00",
            created_by="tests",
            notes=None,
        ),
    )
    monkeypatch.setattr(
        "shellbrain.periphery.admin.doctor.inspect_role_safety",
        lambda dsn: ["unsafe"] if "app" in dsn else ["admin-ok"],
    )
    monkeypatch.setattr("shellbrain.periphery.admin.doctor._fetch_schema_revision", lambda dsn: "20260320_0008")

    report = build_doctor_report(
        app_dsn="postgresql+psycopg://shellbrain_app:shellbrain@localhost:5432/shellbrain_live",
        admin_dsn="postgresql+psycopg://shellbrain_admin:shellbrain_admin@localhost:5432/shellbrain_live",
        backup_root=tmp_path,
    )

    assert report["instance"]["instance_mode"] == "live"
    assert report["app_role_warnings"] == ["unsafe"]
    assert report["admin_role_warnings"] == ["admin-ok"]
    assert report["latest_backup"]["backup_id"] == "b-1"
    assert isinstance(report["backup_age_seconds"], int)
    assert "disk_free_bytes" in report
