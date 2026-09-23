"""Verify installers retain setup flags without exposing public init."""

from types import SimpleNamespace

from app.entrypoints.bootstrap import main
from app.startup import migrations, runtime_admin


def test_bootstrap_forwards_storage_and_setup_flags(monkeypatch, tmp_path):
    captured = {}

    def initialize(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(outcome="ready", lines=[], exit_code=0)

    monkeypatch.setattr(runtime_admin, "run_init", initialize)
    monkeypatch.setattr(
        runtime_admin, "should_register_repo_during_init", lambda **kw: True
    )
    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--storage",
                "external",
                "--admin-dsn",
                "test-dsn",
                "--skip-model-download",
                "--no-host-assets",
            ]
        )
        == 0
    )
    assert captured["repo_root"] == tmp_path
    assert captured["storage"] == "external" and captured["admin_dsn"] == "test-dsn"
    assert (
        captured["register_repo_now"]
        and captured["skip_model_download"]
        and captured["skip_host_assets"]
    )


def test_migration_only_never_initializes_machine(monkeypatch):
    called = []
    monkeypatch.setattr(
        migrations, "upgrade_database", lambda: called.append("migration")
    )

    def forbidden(**kwargs):
        raise AssertionError("must not bootstrap machine")

    monkeypatch.setattr(runtime_admin, "run_init", forbidden)
    assert main(["--migrate-only"]) == 0
    assert called == ["migration"]
