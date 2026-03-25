"""Resilience contracts for safety reporting and privilege diagnostics."""

from __future__ import annotations

from pathlib import Path
import sys

from app.periphery.admin.backup import BackupManifest
from app.periphery.admin.doctor import build_doctor_report
from app.periphery.admin.instance_guard import InstanceMetadataRecord
from app.periphery.onboarding.host_assets import install_host_assets

APP_LIVE_DSN = "postgresql+psycopg://app_user:app_password@localhost:5432/shellbrain_live"
ADMIN_LIVE_DSN = "postgresql+psycopg://admin_user:admin_password@localhost:5432/shellbrain_live"


def test_doctor_report_should_tolerate_missing_app_dsn(monkeypatch, tmp_path: Path) -> None:
    """doctor should still produce one report when the app DSN is not configured."""

    monkeypatch.setattr("app.periphery.admin.doctor.list_backups", lambda backup_root: [])
    monkeypatch.setattr("app.periphery.admin.doctor.inspect_role_safety", lambda dsn: ["warn"] if dsn else [])
    monkeypatch.setattr("app.periphery.admin.doctor.try_load_machine_config", lambda: (None, None))
    monkeypatch.setattr(
        "app.periphery.admin.doctor.inspect_host_assets",
        lambda: type(
            "HostInspection",
            (),
            {
                "codex_skill": {"installed": True},
                "claude_skill": {"installed": True},
                "claude_global_hook": {"installed": True, "managed": True},
            },
        )(),
    )
    monkeypatch.setattr(
        "app.periphery.admin.doctor.fetch_instance_metadata",
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
        admin_dsn=ADMIN_LIVE_DSN,
        backup_root=tmp_path,
    )

    assert report["app_dsn_configured"] is False
    assert report["admin_dsn_configured"] is True
    assert report["schema_revision"] is None
    assert report["app_role_warnings"] == []
    assert report["admin_role_warnings"] == ["warn"]
    assert report["config_status"] in {"absent", "ok", "corrupt"}
    assert report["effective_config"]["admin_dsn"] == "postgresql://<redacted>@localhost:5432/shellbrain_live"
    assert report["host_integrations"]["claude_global_hook"]["managed"] is True


def test_doctor_report_should_include_latest_backup_age(monkeypatch, tmp_path: Path) -> None:
    """doctor should summarize backup age and both role-safety channels."""

    monkeypatch.setattr(
        "app.periphery.admin.doctor.list_backups",
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
        "app.periphery.admin.doctor.fetch_instance_metadata",
        lambda dsn: InstanceMetadataRecord(
            instance_id="inst-live",
            instance_mode="live",
            created_at="2026-03-19T00:00:00+00:00",
            created_by="tests",
            notes=None,
        ),
    )
    monkeypatch.setattr(
        "app.periphery.admin.doctor.inspect_role_safety",
        lambda dsn: ["unsafe"] if "app" in dsn else ["admin-ok"],
    )
    monkeypatch.setattr("app.periphery.admin.doctor.try_load_machine_config", lambda: (None, None))
    monkeypatch.setattr(
        "app.periphery.admin.doctor.inspect_host_assets",
        lambda: type(
            "HostInspection",
            (),
            {
                "codex_skill": {"installed": False},
                "claude_skill": {"installed": True},
                "claude_global_hook": {"installed": True, "managed": True},
            },
        )(),
    )
    monkeypatch.setattr("app.periphery.admin.doctor._fetch_schema_revision", lambda dsn: "20260320_0008")

    report = build_doctor_report(
        app_dsn=APP_LIVE_DSN,
        admin_dsn=ADMIN_LIVE_DSN,
        backup_root=tmp_path,
    )

    assert report["instance"]["instance_mode"] == "live"
    assert report["app_role_warnings"] == ["unsafe"]
    assert report["admin_role_warnings"] == ["admin-ok"]
    assert report["latest_backup"]["backup_id"] == "b-1"
    assert isinstance(report["backup_age_seconds"], int)
    assert "disk_free_bytes" in report
    assert report["host_integrations"]["claude_skill"]["installed"] is True


def test_doctor_report_should_surface_the_managed_claude_hook_interpreter(monkeypatch, tmp_path: Path) -> None:
    """doctor should expose the managed Claude hook interpreter path when it is valid."""

    home_root = tmp_path / "home"
    codex_home = home_root / ".codex"
    monkeypatch.setenv("HOME", str(home_root))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setattr("app.periphery.admin.doctor.list_backups", lambda backup_root: [])
    monkeypatch.setattr("app.periphery.admin.doctor.inspect_role_safety", lambda dsn: [])
    monkeypatch.setattr("app.periphery.admin.doctor.try_load_machine_config", lambda: (None, None))
    monkeypatch.setattr("app.periphery.admin.doctor.fetch_instance_metadata", lambda dsn: None)

    install_host_assets(host_mode="claude", force=False)

    report = build_doctor_report(
        app_dsn=None,
        admin_dsn=None,
        backup_root=tmp_path,
    )

    assert report["host_integrations"]["claude_global_hook"]["managed"] is True
    assert report["host_integrations"]["claude_global_hook"]["command_executable"] == str(Path(sys.executable).resolve())
    assert report["host_integrations"]["claude_global_hook"]["executable_exists"] is True
    assert "host_integration_warning" not in report


def test_doctor_report_should_warn_when_the_managed_claude_hook_interpreter_is_missing(monkeypatch, tmp_path: Path) -> None:
    """doctor should emit an actionable warning when the managed Claude hook interpreter is gone."""

    home_root = tmp_path / "home"
    settings_path = home_root / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        """
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "/tmp/missing-shellbrain-python -m app.periphery.identity.claude_runtime session-start # shellbrain-managed:session-start"
          }
        ]
      }
    ]
  }
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home_root))
    monkeypatch.setenv("CODEX_HOME", str(home_root / ".codex"))
    monkeypatch.setattr("app.periphery.admin.doctor.list_backups", lambda backup_root: [])
    monkeypatch.setattr("app.periphery.admin.doctor.inspect_role_safety", lambda dsn: [])
    monkeypatch.setattr("app.periphery.admin.doctor.try_load_machine_config", lambda: (None, None))
    monkeypatch.setattr("app.periphery.admin.doctor.fetch_instance_metadata", lambda dsn: None)

    report = build_doctor_report(
        app_dsn=None,
        admin_dsn=None,
        backup_root=tmp_path,
    )

    assert report["host_integrations"]["claude_global_hook"]["managed"] is True
    assert report["host_integrations"]["claude_global_hook"]["command_executable"] == str(
        Path("/tmp/missing-shellbrain-python").resolve()
    )
    assert report["host_integrations"]["claude_global_hook"]["executable_exists"] is False
    assert report["host_integration_warning"] == (
        "Claude global hook points at a missing interpreter. Rerun `shellbrain init` to repair it."
    )
