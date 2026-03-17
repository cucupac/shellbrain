"""CLI surface contracts for the packaged shellbrain entrypoint."""

from __future__ import annotations

from pathlib import Path

import pytest

from shellbrain.periphery.cli import main as cli_main
from shellbrain.periphery.cli.hydration import resolve_repo_context


def test_resolve_repo_context_infers_repo_id_from_explicit_repo_root(tmp_path: Path) -> None:
    """repo context resolution should infer repo_id from the resolved repo_root basename."""

    repo_root = tmp_path / "external-repo"
    repo_root.mkdir()

    context = resolve_repo_context(repo_root_arg=str(repo_root), repo_id_arg=None)

    assert context.repo_root == repo_root.resolve()
    assert context.repo_id == "external-repo"


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
    assert "--repo-root" in output
    assert "--no-sync" not in output
    assert "create" in output
    assert "read" in output
    assert "update" in output
    assert "events" in output


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

    monkeypatch.setattr("shellbrain.boot.migrations.upgrade_database", lambda: calls.append("migrated"))

    exit_code = cli_main.main(["admin", "migrate"])

    assert exit_code == 0
    assert calls == ["migrated"]
    assert "Applied shellbrain schema migrations to head." in capsys.readouterr().out


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
