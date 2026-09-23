"""CLI surface contracts for the packaged shellbrain entrypoint."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import app.entrypoints.cli.main as cli_main
import app.entrypoints.cli.parser.builder as cli_parser
import app.entrypoints.cli.runner as cli_runner
from app.entrypoints.cli.handlers.cli_operation import (
    CliOperationEffects,
    run_cli_operation,
)
from app.infrastructure.local_state import operation_registration
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


def test_shellbrain_help_should_explain_the_workflow(capsys):
    with pytest.raises(SystemExit):
        cli_main.main(["--help"])
    output = capsys.readouterr().out
    assert "Use recall for context" in output
    assert "Internal commands:" in output
    assert "shellbrain teach" not in output


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


def test_upgrade_help_should_include_one_example(capsys):
    with pytest.raises(SystemExit):
        cli_main.main(["upgrade", "--help"])
    assert "automatically repair runtime setup" in capsys.readouterr().out


def test_read_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """read help should teach focused querying and pack structure."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["read", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "Internal knowledge-builder endpoint" in output
    assert "Use `concept show` for details and evidence" in output
    assert "Working agents should call `recall`" in output
    assert "shellbrain read --json" in output
    assert "Avoid generic prompts" in output
    assert "explicit_related" in output
    assert "implicit_related" in output
    assert "concepts" in output
    assert "deposit-addresses" in output


def test_recall_help_should_describe_read_only_synthesis_contract(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """recall help should describe the worker-facing natural-language query."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["recall", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert (
        'shellbrain recall "What context matters for this migration lock timeout?"'
        in output
    )
    assert "normal working-agent interface" in output
    assert "not internal commands like `read`, `events`, or `concept show`" in output
    assert "natural-language query" in output
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
    assert "internal knowledge-builder concept graph work" in output
    assert "Internal agents may use" in output
    assert "future librarian integration" not in output
    assert "shellbrain concept show --json" in output
    assert "shellbrain concept add --json" in output
    assert "shellbrain concept update --json" in output
    with pytest.raises(SystemExit) as show_exc:
        cli_main.main(["concept", "show", "--help"])
    assert show_exc.value.code == 0
    show_output = capsys.readouterr().out
    assert "Internal recall-agent read-only endpoint" in show_output
    assert "progressive disclosure" in show_output
    assert "Working agents should call `recall`" in show_output
    with pytest.raises(SystemExit) as add_exc:
        cli_main.main(["concept", "add", "--help"])
    assert add_exc.value.code == 0
    assert "--json-file" in capsys.readouterr().out


def test_concept_parser_should_require_subcommand_and_accept_payloads(
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

    show_args = parser.parse_args(
        [
            "concept",
            "show",
            "--json",
            '{"schema_version":"concept.v1","concept":"deposit-addresses","include":["claims"]}',
        ]
    )
    assert show_args.command == "concept"
    assert show_args.concept_command == "show"

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
        cli_runner._load_payload(file_args.json_text, file_args.json_file)["actions"][
            0
        ]["type"]
        == "update_concept"
    )


def test_load_payload_rejects_non_object_json(tmp_path: Path) -> None:
    """operation payloads should always be JSON objects."""

    with pytest.raises(ValueError, match="JSON payload must be an object"):
        cli_runner._load_payload("[]", None)

    payload_file = tmp_path / "payload.json"
    payload_file.write_text('"not an object"', encoding="utf-8")

    with pytest.raises(ValueError, match="JSON payload must be an object"):
        cli_runner._load_payload(None, str(payload_file))


def test_scenario_parser_should_require_record_subcommand() -> None:
    """scenario should expose only an explicit record operation."""

    parser = cli_parser.build_parser()

    with pytest.raises(SystemExit) as bare_exc:
        parser.parse_args(
            [
                "scenario",
                "--json",
                '{"schema_version":"scenario.v1","scenario":{}}',
            ]
        )
    assert bare_exc.value.code == 2

    args = parser.parse_args(
        [
            "scenario",
            "record",
            "--json",
            (
                '{"schema_version":"scenario.v1","scenario":{"episode_id":"ep",'
                '"outcome":"abandoned","problem_memory_id":"mem-problem",'
                '"opened_event_id":"evt-open","closed_event_id":"evt-close"}}'
            ),
        ]
    )
    assert args.command == "scenario"
    assert args.scenario_command == "record"


def test_events_help_should_include_one_example(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """events help should explain fresh episodic evidence lookup."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["events", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "Internal-agent endpoint" in output
    assert "Recall agents should run this before private reads" in output
    assert "Session knowledge-builder agents" in output
    assert "shellbrain events --json" in output
    assert "inline transcript sync" in output
    assert "after_seq" in output
    assert "up_to_seq" in output


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
    assert "structural_memory_relations" in output
    assert "problem_attempts" not in output


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


def test_scenario_record_help_should_describe_problem_windows(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """scenario record help should describe bounded problem-solving runs."""

    with pytest.raises(SystemExit) as excinfo:
        cli_main.main(["scenario", "record", "--help"])

    assert excinfo.value.code == 0
    output = capsys.readouterr().out
    assert "Internal knowledge-builder endpoint" in output
    assert "`scenario record` writes a problem_run, not a memory" in output
    assert "problem_runs" in output
    assert "token" in output
    assert "ROI" in output
    assert "solved" in output
    assert "abandoned" in output
    assert "problem_memory_id" in output
    assert "solution_memory_id" in output
    assert "opened_event_id" in output
    assert "closed_event_id" in output
    assert "scenario.v1" in output


def test_admin_help_should_include_one_example(capsys):
    with pytest.raises(SystemExit):
        cli_main.main(["admin", "--help"])
    output = capsys.readouterr().out
    assert "backup" in output and "recall" in output
    assert "migrate" not in output


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

    monkeypatch.setattr(
        cli_runner, "run_operation_command", _fake_run_operation_command
    )

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

    monkeypatch.setattr(
        cli_runner, "run_operation_command", _fake_run_operation_command
    )

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


def test_main_dispatches_recall_query(monkeypatch, tmp_path: Path) -> None:
    """recall should dispatch one positional natural-language query."""

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
                "brief": {"memories": ["stub"], "code": []},
                "fallback_reason": None,
            },
        }
        captured["result"] = result
        return result

    monkeypatch.setattr(
        cli_runner, "run_operation_command", _fake_run_operation_command
    )

    exit_code = cli_main.main(
        [
            "--repo-root",
            str(repo_root),
            "recall",
            "What context matters for this migration lock timeout?",
        ]
    )

    assert exit_code == 0
    assert captured["command"] == "recall"
    assert captured["payload"] == {
        "query": "What context matters for this migration lock timeout?"
    }


def test_main_dispatches_snapshot_without_json(monkeypatch, tmp_path: Path) -> None:
    """snapshot should be a zero-payload worker command."""

    repo_root = tmp_path / "snapshot-repo"
    repo_root.mkdir()
    captured: dict[str, object] = {}

    def _fake_run_operation_command(**kwargs):
        captured["command"] = kwargs["command"]
        captured["payload"] = kwargs["payload"]
        captured["repo_context"] = kwargs["repo_context"]
        return {"status": "ok", "data": {"result": "created"}}

    monkeypatch.setattr(
        cli_runner, "run_operation_command", _fake_run_operation_command
    )

    exit_code = cli_main.main(
        ["--repo-root", str(repo_root), "--repo-id", "repo-snapshot", "snapshot"]
    )

    assert exit_code == 0
    assert captured["command"] == "snapshot"
    assert captured["payload"] == {}
    resolved_context = captured["repo_context"]
    assert resolved_context.repo_root == repo_root.resolve()
    assert resolved_context.repo_id == "repo-snapshot"


def test_main_returns_nonzero_for_error_operation_envelope(
    monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """operation error envelopes should render normally and produce a failing exit."""

    repo_root = tmp_path / "error-repo"
    repo_root.mkdir()

    def _fake_run_operation_command(**kwargs):
        return {
            "status": "error",
            "errors": [{"code": "schema_error", "message": "bad request"}],
        }

    monkeypatch.setattr(
        cli_runner, "run_operation_command", _fake_run_operation_command
    )

    exit_code = cli_main.main(
        [
            "--repo-root",
            str(repo_root),
            "read",
            "--json",
            '{"query":"what should fail?"}',
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert (
        captured.out.strip()
        == '{"status":"error","errors":[{"code":"schema_error","message":"bad request"}]}'
    )
    assert captured.err == ""


def test_inner_agent_read_only_mode_allows_only_read_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """inner-agent read-only mode should reject write routes before dispatch."""

    monkeypatch.setenv("SHELLBRAIN_INNER_AGENT_MODE", "build_context")

    cli_runner._enforce_inner_agent_mode("read")
    cli_runner._enforce_inner_agent_mode("events")
    cli_runner._enforce_inner_agent_mode("concept:show")
    with pytest.raises(ValueError):
        cli_runner._enforce_inner_agent_mode("recall")
    with pytest.raises(ValueError):
        cli_runner._enforce_inner_agent_mode("memory:add")
    with pytest.raises(ValueError):
        cli_runner._enforce_inner_agent_mode("concept:update")
    with pytest.raises(ValueError):
        cli_runner._enforce_inner_agent_mode("scenario:record")


def test_inner_agent_synthesis_mode_rejects_all_shellbrain_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """synthesis-only recall should not be able to issue nested Shellbrain reads."""

    monkeypatch.setenv("SHELLBRAIN_INNER_AGENT_MODE", "build_context_synthesis")

    for command in (
        "events",
        "read",
        "concept:show",
        "recall",
        "memory:add",
        "concept:update",
        "scenario:record",
    ):
        with pytest.raises(ValueError):
            cli_runner._enforce_inner_agent_mode(command)


def test_inner_agent_build_knowledge_mode_allows_only_builder_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """build_knowledge mode should allow knowledge writes but reject public/admin routes."""

    monkeypatch.setenv("SHELLBRAIN_INNER_AGENT_MODE", "build_knowledge")

    for command in (
        "events",
        "read",
        "concept:show",
        "memory:add",
        "memory:update",
        "concept:add",
        "concept:update",
        "scenario:record",
    ):
        cli_runner._enforce_inner_agent_mode(command)
    for command in ("recall", "admin", "init", "upgrade"):
        with pytest.raises(ValueError):
            cli_runner._enforce_inner_agent_mode(command)


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

    monkeypatch.setattr(
        cli_runner, "run_operation_command", _fake_run_operation_command
    )

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


def test_cli_operation_should_prepare_managed_runtime_before_db_audit(
    tmp_path: Path,
) -> None:
    """operation orchestration should give managed Docker one recovery chance first."""

    repo_context = SimpleNamespace(repo_root=tmp_path, repo_id="repo")
    calls: list[str] = []
    effects = CliOperationEffects(
        new_invocation_id=lambda: "inv-1",
        resolve_caller_identity=lambda: SimpleNamespace(
            caller_identity=None, error=None
        ),
        set_operation_context=lambda context: calls.append("context") or "token",
        reset_operation_context=lambda token: calls.append("reset"),
        ensure_managed_runtime_ready=lambda: calls.append("runtime"),
        warn_or_fail_on_unsafe_app_role=lambda: calls.append("audit"),
        ensure_repo_registration=lambda **kwargs: calls.append("register"),
        ensure_shadow_baseline=lambda **kwargs: calls.append("baseline"),
        maybe_start_sync=lambda context: calls.append("sync") or False,
        update_operation_polling_status=lambda **kwargs: calls.append("poll"),
    )

    result = run_cli_operation(
        command="read",
        payload={"query": "x"},
        repo_context=repo_context,
        repo_id_override=None,
        no_sync=False,
        dispatch_operation=lambda command, payload, context: (
            calls.append("dispatch") or {"status": "ok", "data": {}}
        ),
        effects=effects,
    )

    assert result["status"] == "ok"
    assert calls == [
        "context",
        "runtime",
        "audit",
        "register",
        "dispatch",
        "baseline",
        "sync",
        "poll",
        "reset",
    ]


def test_operational_command_should_fail_cleanly_when_managed_runtime_is_unavailable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """managed runtime readiness failures should use the existing clean CLI error path."""

    repo_root = tmp_path / "runtime-down-repo"
    repo_root.mkdir()
    resets: list[object] = []
    runtime = SimpleNamespace(
        resolve_repo_context=lambda **_kwargs: SimpleNamespace(
            repo_root=repo_root, repo_id="repo", registration_root=repo_root
        ),
        new_invocation_id=lambda: "inv-1",
        resolve_caller_identity=lambda: SimpleNamespace(
            caller_identity=None, error=None
        ),
        set_operation_context=lambda context: "token",
        reset_operation_context=lambda token: resets.append(token),
        ensure_managed_runtime_ready=lambda: (_ for _ in ()).throw(
            RuntimeError("managed runtime unavailable")
        ),
        warn_or_fail_on_unsafe_app_role=lambda: (_ for _ in ()).throw(
            AssertionError("unexpected audit")
        ),
        ensure_repo_registration=lambda **kwargs: None,
        ensure_shadow_baseline=lambda **kwargs: None,
        maybe_start_sync=lambda context: False,
        update_operation_polling_status=lambda **kwargs: None,
    )

    exit_code = cli_runner.main(
        [
            "--repo-root",
            str(repo_root),
            "read",
            "--json",
            '{"query":"what should fail?"}',
        ],
        runtime=runtime,
    )

    assert exit_code == 1
    assert "managed runtime unavailable" in capsys.readouterr().err
    assert resets == ["token"]


def test_upgrade_should_delegate_to_hosted_upgrader(monkeypatch) -> None:
    """upgrade should delegate to the hosted upgrader and propagate its exit code."""

    monkeypatch.setattr(
        "app.infrastructure.system.package_upgrade.run_upgrade", lambda: 23
    )

    exit_code = cli_main.main(["upgrade"])

    assert exit_code == 23


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

    operation_registration.ensure_repo_registration_for_operation(
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

    operation_registration.ensure_repo_registration_for_operation(
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
