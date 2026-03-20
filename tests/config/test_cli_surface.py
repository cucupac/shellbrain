"""CLI surface contracts for the packaged shellbrain entrypoint."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.periphery.cli import main as cli_main
from app.periphery.cli.hydration import resolve_repo_context


def test_resolve_repo_context_infers_repo_id_from_explicit_repo_root(tmp_path: Path) -> None:
    """repo context resolution should fall back to one weak-local repo id outside git."""

    repo_root = tmp_path / "external-repo"
    repo_root.mkdir()

    context = resolve_repo_context(repo_root_arg=str(repo_root), repo_id_arg=None)

    assert context.repo_root == repo_root.resolve()
    assert context.repo_id.startswith("external-repo::")


def test_resolve_repo_context_preserves_explicit_repo_id(tmp_path: Path) -> None:
    """repo context resolution should preserve an explicit repo_id override."""

    repo_root = tmp_path / "external-repo"
    repo_root.mkdir()

    context = resolve_repo_context(repo_root_arg=str(repo_root), repo_id_arg="repo-override")

    assert context.repo_root == repo_root.resolve()
    assert context.repo_id == "repo-override"


def test_shellbrain_help_should_explain_the_workflow(capsys: pytest.CaptureFixture[str]) -> None:
    """top-level help should explain the Shellbrain mental model and session protocol."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "case-based memory system" in output
    assert "Avoid generic prompts like" in output
    assert "At session end" in output
    assert "utility_vote" in output
    assert "shellbrain admin migrate" in output
    assert "shellbrain admin backup create" in output
    assert "shellbrain admin doctor" in output
    assert "pipx install shellbrain" in output
    assert "shellbrain init" in output
    assert "--repo-root" in output
    assert "--no-sync" not in output
    assert "create" in output
    assert "read" in output
    assert "update" in output
    assert "events" in output


def test_init_help_should_include_bootstrap_examples(capsys: pytest.CaptureFixture[str]) -> None:
    """init help should explain the managed bootstrap path and advanced overrides."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["init", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "Bootstrap or repair" in output
    assert "shellbrain init --host claude" in output
    assert "--skip-model-download" in output
    assert "--repo-id" in output


def test_read_help_should_include_one_example(capsys: pytest.CaptureFixture[str]) -> None:
    """read help should teach focused querying and pack structure."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["read", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "shellbrain read --json" in output
    assert "Avoid generic prompts" in output
    assert "explicit_related" in output
    assert "implicit_related" in output


def test_events_help_should_include_one_example(capsys: pytest.CaptureFixture[str]) -> None:
    """events help should explain fresh episodic evidence lookup."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["events", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "shellbrain events --json" in output
    assert "inline transcript sync" in output


def test_create_help_should_include_one_example(capsys: pytest.CaptureFixture[str]) -> None:
    """create help should explain memory-kind choice and attempt-link rules."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["create", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "shellbrain create --json" in output
    assert "failed_tactic" in output
    assert "memory.links.problem_id" in output


def test_update_help_should_include_one_example(capsys: pytest.CaptureFixture[str]) -> None:
    """update help should expose the supported update types."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["update", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "shellbrain update --json" in output
    assert "utility_vote" in output
    assert "-1.0" in output
    assert "positive = helpful" in output
    assert "fact_update_link" in output
    assert "association_link" in output


def test_admin_help_should_include_one_example(capsys: pytest.CaptureFixture[str]) -> None:
    """admin help should always include one minimal example."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "--help"])

    assert excinfo.value.code == 0
    assert "shellbrain admin migrate" in capsys.readouterr().out


def test_admin_migrate_help_should_include_one_example(capsys: pytest.CaptureFixture[str]) -> None:
    """admin migrate help should always include one minimal example."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "migrate", "--help"])

    assert excinfo.value.code == 0
    assert "Apply packaged Alembic migrations" in capsys.readouterr().out


def test_admin_backup_help_should_include_backup_examples(capsys: pytest.CaptureFixture[str]) -> None:
    """admin backup help should explain the first-class backup workflow."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "backup", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "backup create" in output
    assert "backup verify" in output
    assert "backup restore" in output


def test_admin_doctor_help_should_include_one_example(capsys: pytest.CaptureFixture[str]) -> None:
    """admin doctor help should explain the safety report path."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "doctor", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "safety report" in output
    assert "--repo-root" in output


def test_admin_install_claude_hook_help_should_include_one_example(capsys: pytest.CaptureFixture[str]) -> None:
    """admin install-claude-hook help should explain the trusted Claude setup step."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "install-claude-hook", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "SessionStart hook" in output
    assert "install-claude-hook" in output


def test_admin_session_state_help_should_include_management_examples(capsys: pytest.CaptureFixture[str]) -> None:
    """admin session-state help should expose inspect, clear, and gc management paths."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "session-state", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "session-state inspect" in output
    assert "session-state clear" in output
    assert "session-state gc" in output


def test_main_accepts_repo_targeting_flags_before_subcommand(monkeypatch, tmp_path: Path) -> None:
    """repo-targeting flags should work before the operational subcommand."""

    repo_root = tmp_path / "before-repo"
    repo_root.mkdir()
    captured: dict[str, object] = {}
    sync_calls: list[object] = []

    def _fake_dispatch(command: str, payload: dict[str, object], repo_context) -> dict[str, object]:
        captured["command"] = command
        captured["payload"] = payload
        captured["repo_context"] = repo_context
        return {"status": "ok", "data": {"memory_id": "mem-1"}}

    monkeypatch.setattr(cli_main, "_warn_or_fail_on_unsafe_app_role", lambda: None)
    monkeypatch.setattr(cli_main, "_dispatch_operation_command", _fake_dispatch)
    monkeypatch.setattr(cli_main, "_print_operation_result", lambda result: captured.setdefault("result", result))
    monkeypatch.setattr(cli_main, "_maybe_start_sync", lambda repo_context: sync_calls.append(repo_context))

    exit_code = cli_main.main(
        [
            "--repo-root",
            str(repo_root),
            "--repo-id",
            "repo-before",
            "read",
            "--json",
            '{"query":"what should I recall?"}',
        ]
    )

    assert exit_code == 0
    assert captured["command"] == "read"
    assert captured["payload"] == {"query": "what should I recall?"}
    resolved_context = captured["repo_context"]
    assert resolved_context.repo_root == repo_root.resolve()
    assert resolved_context.repo_id == "repo-before"
    assert sync_calls == [resolved_context]


def test_main_accepts_repo_targeting_flags_after_subcommand(monkeypatch, tmp_path: Path) -> None:
    """repo-targeting flags should also work after the operational subcommand."""

    repo_root = tmp_path / "after-repo"
    repo_root.mkdir()
    captured: dict[str, object] = {}

    def _fake_dispatch(command: str, payload: dict[str, object], repo_context) -> dict[str, object]:
        captured["command"] = command
        captured["payload"] = payload
        captured["repo_context"] = repo_context
        return {"status": "ok", "data": {"episode_id": "ep-1"}}

    monkeypatch.setattr(cli_main, "_warn_or_fail_on_unsafe_app_role", lambda: None)
    monkeypatch.setattr(cli_main, "_dispatch_operation_command", _fake_dispatch)
    monkeypatch.setattr(cli_main, "_print_operation_result", lambda result: None)
    monkeypatch.setattr(cli_main, "_maybe_start_sync", lambda repo_context: None)

    exit_code = cli_main.main(
        [
            "events",
            "--repo-root",
            str(repo_root),
            "--repo-id",
            "repo-after",
            "--json",
            '{"limit":5}',
        ]
    )

    assert exit_code == 0
    assert captured["command"] == "events"
    assert captured["payload"] == {"limit": 5}
    resolved_context = captured["repo_context"]
    assert resolved_context.repo_root == repo_root.resolve()
    assert resolved_context.repo_id == "repo-after"


def test_no_sync_should_prevent_poller_start(monkeypatch, tmp_path: Path) -> None:
    """--no-sync should suppress repo-local poller startup after a successful command."""

    repo_root = tmp_path / "quiet-repo"
    repo_root.mkdir()
    sync_calls: list[object] = []

    monkeypatch.setattr(cli_main, "_warn_or_fail_on_unsafe_app_role", lambda: None)
    monkeypatch.setattr(cli_main, "_dispatch_operation_command", lambda *args, **kwargs: {"status": "ok", "data": {}})
    monkeypatch.setattr(cli_main, "_print_operation_result", lambda result: None)
    monkeypatch.setattr(cli_main, "_maybe_start_sync", lambda repo_context: sync_calls.append(repo_context))

    exit_code = cli_main.main(
        [
            "--repo-root",
            str(repo_root),
            "read",
            "--no-sync",
            "--json",
            '{"query":"keep this quiet"}',
        ]
    )

    assert exit_code == 0
    assert sync_calls == []


def test_admin_migrate_should_invoke_packaged_migration_runner(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin migrate should delegate to the packaged migration runner."""

    calls: list[str] = []

    monkeypatch.setattr("app.boot.migrations.upgrade_database", lambda: calls.append("migrated"))

    exit_code = cli_main.main(["admin", "migrate"])

    assert exit_code == 0
    assert calls == ["migrated"]
    assert "Applied shellbrain schema migrations to head." in capsys.readouterr().out


def test_operational_command_should_fail_cleanly_when_app_role_is_unsafe(
    monkeypatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """unsafe app-role failures should return exit code 1 without a traceback."""

    repo_root = tmp_path / "unsafe-role-repo"
    repo_root.mkdir()

    monkeypatch.setattr(cli_main, "_warn_or_fail_on_unsafe_app_role", lambda: (_ for _ in ()).throw(ValueError("unsafe role")))
    monkeypatch.setattr(cli_main, "_dispatch_operation_command", lambda *args, **kwargs: {"status": "ok", "data": {}})
    monkeypatch.setattr(cli_main, "_print_operation_result", lambda result: None)

    exit_code = cli_main.main(
        [
            "--repo-root",
            str(repo_root),
            "read",
            "--json",
            '{"query":"what should I recall?"}',
        ]
    )

    assert exit_code == 1
    assert "unsafe role" in capsys.readouterr().err


def test_admin_backup_create_should_dispatch_to_backup_module(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin backup create should print the created manifest as JSON."""

    from app.periphery.admin.backup import BackupManifest

    monkeypatch.setattr("app.boot.admin_db.get_admin_db_dsn", lambda: "postgresql+psycopg://admin:pw@localhost:5432/test_admin")
    monkeypatch.setattr("app.boot.admin_db.get_backup_dir", lambda: Path("/tmp/shellbrain-backups"))
    monkeypatch.setattr("app.boot.admin_db.get_backup_mirror_dir", lambda: None)
    monkeypatch.setattr(
        "app.periphery.admin.backup.create_backup",
        lambda **kwargs: BackupManifest(
            backup_id="b-1",
            instance_id="i-1",
            instance_mode="live",
            source={"database": "shellbrain", "fingerprint": "abc", "host": "localhost", "port": "5432", "user": "admin"},
            schema_revision="20260320_0008",
            created_at="2026-03-19T00:00:00+00:00",
            artifact_filename="artifact.sql.gz",
            artifact_sha256="deadbeef",
            artifact_size_bytes=10,
            compression="gzip",
        ),
    )

    exit_code = cli_main.main(["admin", "backup", "create"])

    assert exit_code == 0
    assert '"backup_id": "b-1"' in capsys.readouterr().out


def test_admin_doctor_should_print_structured_report(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin doctor should print one JSON safety report."""

    monkeypatch.setattr("app.boot.db.get_optional_db_dsn", lambda: "postgresql+psycopg://app:pw@localhost:5432/test_app")
    monkeypatch.setattr("app.boot.admin_db.get_optional_admin_db_dsn", lambda: "postgresql+psycopg://admin:pw@localhost:5432/test_admin")
    monkeypatch.setattr("app.boot.admin_db.get_backup_dir", lambda: Path("/tmp/shellbrain-backups"))
    monkeypatch.setattr(
        "app.periphery.admin.doctor.build_doctor_report",
        lambda **kwargs: {"instance": {"instance_mode": "live"}, "backup_count": 1},
    )

    exit_code = cli_main.main(["admin", "doctor"])

    assert exit_code == 0
    assert '"backup_count": 1' in capsys.readouterr().out


def test_init_should_print_outcome_and_return_mapped_exit_code(
    monkeypatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """init should print the stable outcome prefix and forward the mapped exit code."""

    from app.periphery.admin.init import InitResult

    repo_root = tmp_path / "init-repo"
    repo_root.mkdir()

    monkeypatch.setattr(
        "app.periphery.admin.init.run_init",
        lambda **kwargs: InitResult(
            outcome="repaired",
            lines=["Managed instance: shellbrain-postgres-test", "Repo: example/repo"],
        ),
    )

    exit_code = cli_main.main(["init", "--repo-root", str(repo_root)])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert output.splitlines()[0] == "Outcome: repaired"
    assert "Managed instance: shellbrain-postgres-test" in output


def test_init_should_map_no_claude_to_host_none(monkeypatch, tmp_path: Path) -> None:
    """init should disable Claude integration when --no-claude is provided."""

    from app.periphery.admin.init import InitResult

    repo_root = tmp_path / "init-no-claude"
    repo_root.mkdir()
    captured: dict[str, object] = {}

    def _fake_run_init(**kwargs):
        captured.update(kwargs)
        return InitResult(outcome="noop", lines=[])

    monkeypatch.setattr("app.periphery.admin.init.run_init", _fake_run_init)

    exit_code = cli_main.main(["init", "--repo-root", str(repo_root), "--host", "claude", "--no-claude"])

    assert exit_code == 0
    assert captured["host_mode"] == "none"


def test_missing_repo_root_should_fail_fast(capsys: pytest.CaptureFixture[str]) -> None:
    """explicit repo-root overrides should fail fast when the directory does not exist."""

    missing_repo_root = Path(__file__).resolve().parent / "missing-repo-root"
    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(
            [
                "--repo-root",
                str(missing_repo_root),
                "read",
                "--json",
                '{"query":"does this exist?"}',
            ]
        )

    assert excinfo.value.code == 2
    assert "repo_root does not exist" in capsys.readouterr().err
