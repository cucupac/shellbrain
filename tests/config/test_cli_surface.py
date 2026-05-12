"""CLI surface contracts for the packaged shellbrain entrypoint."""

from __future__ import annotations

from pathlib import Path

import pytest

import app.entrypoints.cli.main as cli_main
import app.entrypoints.cli.parser.builder as cli_parser
import app.entrypoints.cli.runner as cli_runner
import app.startup.cli as startup_cli
from app.startup.repo_context import RepoContext, resolve_repo_context


def test_resolve_repo_context_infers_repo_id_from_explicit_repo_root(
    tmp_path: Path,
) -> None:
    """repo context resolution should fall back to one weak-local repo id outside git."""

    repo_root = tmp_path / "external-repo"
    repo_root.mkdir()

    context = resolve_repo_context(repo_root_arg=str(repo_root), repo_id_arg=None)

    assert context.repo_root == repo_root.resolve()
    assert context.repo_id.startswith("external-repo::")
    assert context.registration_root == repo_root.resolve()


def test_resolve_repo_context_preserves_explicit_repo_id(tmp_path: Path) -> None:
    """repo context resolution should preserve an explicit repo_id override."""

    repo_root = tmp_path / "external-repo"
    repo_root.mkdir()

    context = resolve_repo_context(
        repo_root_arg=str(repo_root), repo_id_arg="repo-override"
    )

    assert context.repo_root == repo_root.resolve()
    assert context.repo_id == "repo-override"
    assert context.registration_root == repo_root.resolve()


def test_resolve_repo_context_should_not_auto_register_plain_non_git_cwd(
    monkeypatch, tmp_path: Path
) -> None:
    """plain non-git working directories should not become auto-registration targets."""

    monkeypatch.chdir(tmp_path)

    context = resolve_repo_context(repo_root_arg=None, repo_id_arg=None)

    assert context.repo_root == tmp_path.resolve()
    assert context.registration_root is None


def test_resolve_repo_context_should_register_at_git_root_from_subdirectories(
    monkeypatch, tmp_path: Path
) -> None:
    """subdirectory invocations should target the git root for registration."""

    repo_root = tmp_path / "repo"
    subdir = repo_root / "subdir"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)
    monkeypatch.setattr(
        "app.startup.repo_context.resolve_git_root",
        lambda path: repo_root if path == subdir else repo_root,
    )
    monkeypatch.setattr(
        "app.infrastructure.local_state.repo_registration_store.resolve_git_root",
        lambda path: repo_root if path == subdir else repo_root,
    )

    context = resolve_repo_context(repo_root_arg=None, repo_id_arg=None)

    assert context.repo_root == subdir.resolve()
    assert context.registration_root == repo_root.resolve()


def test_shellbrain_help_should_explain_the_workflow(
    capsys: pytest.CaptureFixture[str],
) -> None:
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
    assert "curl -L shellbrain.ai/install | bash" in output
    assert "curl -L shellbrain.ai/upgrade | bash" in output
    assert "shellbrain upgrade" in output
    assert "pipx upgrade shellbrain && shellbrain init" in output
    assert "shellbrain init" in output
    assert "shellbrain metrics" in output
    assert "--repo-root" in output
    assert "--no-sync" not in output
    assert "read" in output
    assert "recall" in output
    assert "memory" in output
    assert "events" in output
    assert "upgrade" in output


def test_shellbrain_version_should_print_the_installed_version(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """top-level version should print the installed package version without requiring a command."""

    monkeypatch.setattr(cli_parser, "_installed_shellbrain_version", lambda: "9.9.9")

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["--version"])

    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == "shellbrain 9.9.9"


def test_init_help_should_include_bootstrap_examples(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """init help should explain the managed bootstrap path and advanced overrides."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["init", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "Bootstrap or repair" in output
    assert "registers a repo only when one is obvious" in output
    assert "--storage" in output
    assert "--admin-dsn" in output
    assert "PostgreSQL database with pgvector" in output
    assert "--no-host-assets" in output
    assert "--skip-model-download" in output
    assert "--repo-id" in output


def test_init_should_forward_storage_flags_to_run_init(
    monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """init should pass storage selection flags through to the bootstrap entrypoint."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        cli_runner, "_resolve_admin_repo_root", lambda repo_root_arg: repo_root
    )
    monkeypatch.setattr(
        startup_cli, "should_register_repo_during_init", lambda **kwargs: False
    )
    monkeypatch.setattr(
        "app.startup.runtime_admin.run_init",
        lambda **kwargs: (
            captured.update(kwargs)
            or type(
                "Result",
                (),
                {"outcome": "initialized", "lines": ["ok"], "exit_code": 0},
            )()
        ),
    )

    exit_code = cli_main.main(
        [
            "init",
            "--storage",
            "external",
            "--admin-dsn",
            "postgresql+psycopg://admin:secret@db.example.com:5432/shellbrain",
        ]
    )

    assert exit_code == 0
    assert captured["storage"] == "external"
    assert (
        captured["admin_dsn"]
        == "postgresql+psycopg://admin:secret@db.example.com:5432/shellbrain"
    )
    assert captured["repo_root"] == repo_root
    assert "Outcome: initialized" in capsys.readouterr().out


def test_upgrade_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """upgrade help should teach the hosted upgrader and manual fallback."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["upgrade", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "hosted upgrade script" in output
    assert "shellbrain.ai/upgrade" in output
    assert "pipx upgrade shellbrain && shellbrain init" in output


def test_metrics_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """metrics help should explain the lightweight dashboard path."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["metrics", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "browser dashboard" in output
    assert "shellbrain metrics" in output
    assert "--days" not in output
    assert "--no-open" not in output


def test_metrics_parser_should_reject_days_and_no_open_flags() -> None:
    """metrics parser should reject removed legacy flags."""

    parser = cli_parser.build_parser()

    with pytest.raises(SystemExit) as days_exc:
        parser.parse_args(["metrics", "--days", "14"])
    assert days_exc.value.code == 2

    with pytest.raises(SystemExit) as no_open_exc:
        parser.parse_args(["metrics", "--no-open"])
    assert no_open_exc.value.code == 2


def test_read_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """read help should teach focused querying and pack structure."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["read", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "shellbrain read --json" in output
    assert "Avoid generic prompts" in output
    assert "explicit_related" in output
    assert "implicit_related" in output
    assert "concepts" in output
    assert "deposit-addresses" in output


def test_recall_help_should_describe_read_only_synthesis_contract(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """recall help should describe the worker-facing synthesis payload."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["recall", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "shellbrain recall --json" in output
    assert "query" in output
    assert "optional `limit`" in output
    assert "optional `current_problem`" in output
    assert "does not mutate" in output


def test_concept_help_should_describe_internal_json_endpoint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """concept help should keep the worker-facing contract small and JSON-first."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["concept", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "Internal JSON-first endpoint" in output
    assert "Internal agents may use" in output
    assert "shellbrain concept add --json" in output
    assert "shellbrain concept update --json" in output
    with pytest.raises(SystemExit) as add_exc:
        cli_main.main(["concept", "add", "--help"])
    assert add_exc.value.code == 0
    assert "--json-file" in capsys.readouterr().out


def test_concept_parser_should_require_add_or_update_and_accept_payloads(
    tmp_path: Path,
) -> None:
    """concept should use the same single-payload-source shape as other operational commands."""

    parser = cli_parser.build_parser()

    with pytest.raises(SystemExit) as bare_exc:
        parser.parse_args(
            [
                "concept",
                "--json",
                '{"schema_version":"concept.v1","actions":[]}',
            ]
        )
    assert bare_exc.value.code == 2

    inline_args = parser.parse_args(
        [
            "concept",
            "add",
            "--json",
            '{"schema_version":"concept.v1","actions":[{"type":"add_concept","slug":"deposit-addresses","name":"Deposit Addresses","kind":"domain"}]}',
        ]
    )
    assert inline_args.command == "concept"
    assert inline_args.concept_command == "add"
    assert inline_args.json_text

    payload_file = tmp_path / "concept.json"
    payload_file.write_text(
        '{"schema_version":"concept.v1","actions":[{"type":"update_concept","concept":"deposit-addresses","name":"Deposit Address Graph"}]}',
        encoding="utf-8",
    )
    file_args = parser.parse_args(
        ["concept", "update", "--json-file", str(payload_file)]
    )
    assert file_args.command == "concept"
    assert file_args.concept_command == "update"
    assert (
        cli_runner._load_payload(file_args.json_text, file_args.json_file)["actions"][0][
            "type"
        ]
        == "update_concept"
    )


def test_events_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """events help should explain fresh episodic evidence lookup."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["events", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "shellbrain events --json" in output
    assert "inline transcript sync" in output


def test_memory_add_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """memory add help should explain memory-kind choice and attempt-link rules."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["memory", "add", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "shellbrain memory add --json" in output
    assert "failed_tactic" in output
    assert "memory.links.problem_id" in output


def test_memory_update_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """memory update help should expose the supported update types."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["memory", "update", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "shellbrain memory update --json" in output
    assert "utility_vote" in output
    assert "-1.0" in output
    assert "positive = helpful" in output
    assert "fact_update_link" in output
    assert "association_link" in output


def test_admin_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin help should always include one minimal example."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "--help"])

    assert excinfo.value.code == 0
    assert "shellbrain admin migrate" in capsys.readouterr().out


def test_admin_migrate_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin migrate help should always include one minimal example."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "migrate", "--help"])

    assert excinfo.value.code == 0
    assert "Apply packaged Alembic migrations" in capsys.readouterr().out


def test_admin_backup_help_should_include_backup_examples(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin backup help should explain the first-class backup workflow."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "backup", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "backup create" in output
    assert "backup verify" in output
    assert "backup restore" in output


def test_admin_doctor_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin doctor help should explain the safety report path."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "doctor", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "safety report" in output
    assert "--repo-root" in output


def test_admin_analytics_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin analytics help should explain the reviewer-agent report path."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "analytics", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "reviewer agents" in output
    assert "--days" in output
    assert "analytics --days 2" in output


def test_admin_install_claude_hook_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin install-claude-hook help should explain the trusted Claude setup step."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "install-claude-hook", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "repo-local" in output
    assert "install-claude-hook" in output


def test_admin_install_host_assets_help_should_include_examples(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin install-host-assets help should explain the personal host-asset repair path."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "install-host-assets", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "Codex, Claude, and Cursor host integrations" in output
    assert "--host" in output
    assert "--force" in output


def test_admin_install_host_assets_should_dispatch_to_installer(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin install-host-assets should print the installer result lines."""

    monkeypatch.setattr(
        "app.infrastructure.host_apps.assets.install_host_assets",
        lambda **kwargs: type(
            "Result", (), {"lines": ["Codex skill: installed at /tmp/codex"]}
        )(),
    )

    exit_code = cli_main.main(["admin", "install-host-assets", "--host", "codex"])

    assert exit_code == 0
    assert "Codex skill: installed at /tmp/codex" in capsys.readouterr().out


def test_admin_backfill_token_usage_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin backfill-token-usage help should explain the retroactive telemetry path."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "backfill-token-usage", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "Backfill normalized token usage" in output
    assert "backfill-token-usage" in output


def test_admin_backfill_token_usage_should_print_the_summary(
    monkeypatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """admin backfill-token-usage should render the backfill summary as JSON."""

    monkeypatch.setattr("app.startup.db.get_engine_instance", lambda: "engine")
    monkeypatch.setattr(
        "app.startup.model_usage_backfill.backfill_model_usage",
        lambda **kwargs: type(
            "Summary",
            (),
            {
                "to_payload": lambda self: {
                    "sessions_examined": 3,
                    "sessions_with_records": 2,
                    "records_attempted": 5,
                }
            },
        )(),
    )

    exit_code = cli_main.main(["admin", "backfill-token-usage"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"sessions_examined": 3' in output
    assert '"records_attempted": 5' in output


def test_admin_analytics_should_print_the_report(
    monkeypatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """admin analytics should render the built analytics report as JSON."""

    monkeypatch.setattr(
        "app.startup.db.get_optional_db_dsn", lambda: "postgresql://app"
    )
    monkeypatch.setattr("app.startup.admin_db.get_optional_admin_db_dsn", lambda: None)
    monkeypatch.setattr(
        "app.infrastructure.db.runtime.engine.get_engine", lambda dsn: f"engine:{dsn}"
    )
    monkeypatch.setattr(
        "app.startup.analytics.build_analytics_report",
        lambda **kwargs: {
            "window": {"days": kwargs["days"]},
            "summary": {"overall_health": "healthy"},
            "strengths": [],
            "failures": [],
            "capability_gaps": [],
            "priorities": [],
            "repo_rollups": [],
        },
    )

    exit_code = cli_main.main(["admin", "analytics", "--days", "5"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"days": 5' in output
    assert '"overall_health": "healthy"' in output


def test_admin_session_state_help_should_include_management_examples(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin session-state help should expose inspect, clear, and gc management paths."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["admin", "session-state", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "session-state inspect" in output
    assert "session-state clear" in output
    assert "session-state gc" in output


def test_main_accepts_repo_targeting_flags_before_subcommand(
    monkeypatch, tmp_path: Path
) -> None:
    """repo-targeting flags should work before the operational subcommand."""

    repo_root = tmp_path / "before-repo"
    repo_root.mkdir()
    captured: dict[str, object] = {}
    sync_calls: list[object] = []

    def _fake_run_operation_command(**kwargs):
        captured["command"] = kwargs["command"]
        captured["payload"] = kwargs["payload"]
        captured["repo_context"] = kwargs["repo_context"]
        result = {"status": "ok", "data": {"memory_id": "mem-1"}}
        captured["result"] = result
        sync_calls.append(kwargs["repo_context"])
        return result

    monkeypatch.setattr(cli_runner, "run_operation_command", _fake_run_operation_command)

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
    assert resolved_context.registration_root == repo_root.resolve()
    assert sync_calls == [resolved_context]


def test_main_accepts_repo_targeting_flags_after_subcommand(
    monkeypatch, tmp_path: Path
) -> None:
    """repo-targeting flags should also work after the operational subcommand."""

    repo_root = tmp_path / "after-repo"
    repo_root.mkdir()
    captured: dict[str, object] = {}

    def _fake_run_operation_command(**kwargs):
        captured["command"] = kwargs["command"]
        captured["payload"] = kwargs["payload"]
        captured["repo_context"] = kwargs["repo_context"]
        return {"status": "ok", "data": {"episode_id": "ep-1"}}

    monkeypatch.setattr(cli_runner, "run_operation_command", _fake_run_operation_command)

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
    assert resolved_context.registration_root == repo_root.resolve()


def test_main_dispatches_recall_json_payload(monkeypatch, tmp_path: Path) -> None:
    """recall should use the same operational JSON dispatch path as read."""

    repo_root = tmp_path / "recall-repo"
    repo_root.mkdir()
    captured: dict[str, object] = {}

    def _fake_run_operation_command(**kwargs):
        captured["command"] = kwargs["command"]
        captured["payload"] = kwargs["payload"]
        captured["repo_context"] = kwargs["repo_context"]
        result = {
            "status": "ok",
            "data": {
                "brief": {"summary": "stub", "sources": []},
                "fallback_reason": None,
            },
        }
        captured["result"] = result
        return result

    monkeypatch.setattr(cli_runner, "run_operation_command", _fake_run_operation_command)

    exit_code = cli_main.main(
        [
            "--repo-root",
            str(repo_root),
            "recall",
            "--json",
            '{"query":"x"}',
        ]
    )

    assert exit_code == 0
    assert captured["command"] == "recall"
    assert captured["payload"] == {"query": "x"}


def test_no_sync_should_prevent_poller_start(monkeypatch, tmp_path: Path) -> None:
    """--no-sync should suppress repo-local poller startup after a successful command."""

    repo_root = tmp_path / "quiet-repo"
    repo_root.mkdir()
    sync_calls: list[object] = []

    def _fake_run_operation_command(**kwargs):
        result = {"status": "ok", "data": {}}
        if not kwargs["no_sync"]:
            sync_calls.append(kwargs["repo_context"])
        return result

    monkeypatch.setattr(cli_runner, "run_operation_command", _fake_run_operation_command)

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


def test_upgrade_should_delegate_to_hosted_upgrader(monkeypatch) -> None:
    """upgrade should delegate to the hosted upgrader and propagate its exit code."""

    monkeypatch.setattr("app.infrastructure.system.package_upgrade.run_upgrade", lambda: 23)

    exit_code = cli_main.main(["upgrade"])

    assert exit_code == 23


def test_admin_migrate_should_invoke_packaged_migration_runner(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin migrate should delegate to the packaged migration runner."""

    calls: list[str] = []

    monkeypatch.setattr(
        "app.startup.migrations.upgrade_database", lambda: calls.append("migrated")
    )

    exit_code = cli_main.main(["admin", "migrate"])

    assert exit_code == 0
    assert calls == ["migrated"]
    assert "Applied shellbrain schema migrations to head." in capsys.readouterr().out


def test_admin_migrate_should_fail_cleanly_when_installed_package_is_older_than_database_revision(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin migrate should print one clear message when the database revision is newer than this package."""

    from app.startup.migrations import DatabaseMigrationConflictError

    monkeypatch.setattr(
        "app.startup.migrations.upgrade_database",
        lambda: (_ for _ in ()).throw(
            DatabaseMigrationConflictError(
                "Installed Shellbrain package (0.1.22) cannot manage database revision 20260415_0012."
            )
        ),
    )

    exit_code = cli_main.main(["admin", "migrate"])

    assert exit_code == 1
    assert "cannot manage database revision 20260415_0012" in capsys.readouterr().err


def test_operational_command_should_fail_cleanly_when_app_role_is_unsafe(
    monkeypatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """unsafe app-role failures should return exit code 1 without a traceback."""

    repo_root = tmp_path / "unsafe-role-repo"
    repo_root.mkdir()

    monkeypatch.setattr(
        cli_runner,
        "run_operation_command",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("unsafe role")),
    )

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


def test_unsafe_app_role_should_warn_instead_of_fail_for_explicit_test_instances(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Disposable test instances should not hard-fail operational commands for unsafe roles."""

    from app.infrastructure.db.admin.instance_guard import InstanceMetadataRecord

    monkeypatch.setattr(
        "app.startup.db.get_db_dsn",
        lambda: (
            "postgresql+psycopg://ci_user:ci_password@localhost:5432/shellbrain_ci_test"
        ),
    )
    monkeypatch.setattr(
        "app.infrastructure.db.admin.instance_guard.inspect_role_safety",
        lambda dsn: ["Current DSN role is superuser-capable."] if dsn else [],
    )
    monkeypatch.setattr(
        "app.infrastructure.db.admin.instance_guard.fetch_instance_metadata",
        lambda dsn: InstanceMetadataRecord(
            instance_id="instance-1",
            instance_mode="test",
            created_at="2026-03-22T00:00:00+00:00",
            created_by="tests",
            notes=None,
        ),
    )

    startup_cli.warn_or_fail_on_unsafe_app_role()

    assert "Unsafe Shellbrain app-role configuration:" in capsys.readouterr().err


def test_admin_backup_create_should_dispatch_to_backup_module(
    monkeypatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """admin backup create should print the created manifest as JSON."""

    from app.infrastructure.db.admin.backups.logical_backup import BackupManifest

    monkeypatch.setattr(
        "app.startup.admin_db.get_admin_db_dsn",
        lambda: (
            "postgresql+psycopg://admin_user:admin_password@localhost:5432/test_admin"
        ),
    )
    monkeypatch.setattr(
        "app.startup.admin_db.get_backup_dir", lambda: Path("/tmp/shellbrain-backups")
    )
    monkeypatch.setattr("app.startup.admin_db.get_backup_mirror_dir", lambda: None)
    monkeypatch.setattr(
        "app.infrastructure.db.admin.backups.logical_backup.create_backup",
        lambda **kwargs: BackupManifest(
            backup_id="b-1",
            instance_id="i-1",
            instance_mode="live",
            source={
                "database": "shellbrain",
                "fingerprint": "abc",
                "host": "localhost",
                "port": "5432",
                "user": "admin",
            },
            schema_revision="20260410_0009",
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

    monkeypatch.setattr(
        "app.startup.db.get_optional_db_dsn",
        lambda: "postgresql+psycopg://app_user:app_password@localhost:5432/test_app",
    )
    monkeypatch.setattr(
        "app.startup.admin_db.get_optional_admin_db_dsn",
        lambda: (
            "postgresql+psycopg://admin_user:admin_password@localhost:5432/test_admin"
        ),
    )
    monkeypatch.setattr(
        "app.startup.admin_db.get_backup_dir", lambda: Path("/tmp/shellbrain-backups")
    )
    monkeypatch.setattr(
        "app.startup.admin_diagnose.build_doctor_report",
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

    from app.startup.runtime_admin import InitResult

    repo_root = tmp_path / "init-repo"
    repo_root.mkdir()

    monkeypatch.setattr(
        "app.startup.runtime_admin.run_init",
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


def test_init_should_forward_register_repo_now_for_explicit_repo_root(
    monkeypatch, tmp_path: Path
) -> None:
    """init should register immediately when one explicit repo root is provided."""

    from app.startup.runtime_admin import InitResult

    repo_root = tmp_path / "init-explicit-repo"
    repo_root.mkdir()
    captured: dict[str, object] = {}

    def _fake_run_init(**kwargs):
        captured.update(kwargs)
        return InitResult(outcome="noop", lines=[])

    monkeypatch.setattr("app.startup.runtime_admin.run_init", _fake_run_init)

    exit_code = cli_main.main(["init", "--repo-root", str(repo_root)])

    assert exit_code == 0
    assert captured["register_repo_now"] is True


def test_init_should_forward_no_host_assets(monkeypatch, tmp_path: Path) -> None:
    """init should forward the no-host-assets flag into the init runner."""

    from app.startup.runtime_admin import InitResult

    repo_root = tmp_path / "init-no-host-assets"
    repo_root.mkdir()
    captured: dict[str, object] = {}

    def _fake_run_init(**kwargs):
        captured.update(kwargs)
        return InitResult(outcome="noop", lines=[])

    monkeypatch.setattr("app.startup.runtime_admin.run_init", _fake_run_init)

    exit_code = cli_main.main(
        ["init", "--repo-root", str(repo_root), "--no-host-assets"]
    )

    assert exit_code == 0
    assert captured["skip_host_assets"] is True


def test_ensure_repo_registration_for_operation_should_register_when_machine_state_is_ready(
    monkeypatch, tmp_path: Path
) -> None:
    """operational commands should auto-register one repo before dispatch when possible."""

    registration_root = tmp_path / "repo"
    registration_root.mkdir()
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "app.infrastructure.local_state.machine_config_store.try_load_machine_config",
        lambda: (type("Config", (), {"machine_instance_id": "inst-1"})(), None),
    )
    monkeypatch.setattr(
        "app.infrastructure.local_state.repo_registration_store.register_repo_for_target",
        lambda **kwargs: calls.append(kwargs) or (None, True),
    )

    startup_cli.ensure_repo_registration_for_operation(
        repo_context=RepoContext(
            repo_root=registration_root,
            repo_id="repo-id",
            registration_root=registration_root,
        ),
        repo_id_override="repo-id",
    )

    assert calls == [
        {
            "repo_root": registration_root,
            "machine_instance_id": "inst-1",
            "explicit_repo_id": "repo-id",
        }
    ]


def test_ensure_repo_registration_for_operation_should_skip_when_no_registration_target_exists(
    monkeypatch,
) -> None:
    """operational commands should not auto-register arbitrary non-git directories by default."""

    monkeypatch.setattr(
        "app.infrastructure.local_state.repo_registration_store.register_repo_for_target",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("register_repo_for_target should not be called")
        ),
    )

    startup_cli.ensure_repo_registration_for_operation(
        repo_context=RepoContext(
            repo_root=Path("/tmp/non-repo"),
            repo_id="repo-id",
            registration_root=None,
        ),
        repo_id_override=None,
    )


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
