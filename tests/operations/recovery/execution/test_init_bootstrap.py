"""Bootstrap and repair contracts for the managed init flow."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

from shellbrain.periphery.admin import init as init_module
from shellbrain.periphery.admin.machine_state import BackupState, DatabaseState, EmbeddingRuntimeState, MachineConfig, ManagedInstanceState
from shellbrain.periphery.admin.repo_state import RepoRegistration


def test_run_init_should_block_when_corrupt_config_cannot_be_recovered(tmp_path: Path, monkeypatch) -> None:
    """init should stop with blocked_config_corrupt when corrupt machine state cannot be rediscovered."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_root = tmp_path / "home"
    preserved = home_root / "config.corrupt.20260319T000000Z.toml"
    captured_stub: dict[str, str | None] = {}

    monkeypatch.setattr(init_module, "get_shellbrain_home", lambda: home_root)
    monkeypatch.setattr(init_module, "_acquire_init_lock", lambda: nullcontext())
    monkeypatch.setattr(init_module, "_ensure_dependencies", lambda: None)
    monkeypatch.setattr(init_module, "try_load_machine_config", lambda: (None, "corrupt toml"))
    monkeypatch.setattr(init_module, "backup_corrupt_machine_config", lambda: preserved)
    monkeypatch.setattr(init_module, "_recover_machine_config_from_docker", lambda: None)
    monkeypatch.setattr("shellbrain.periphery.admin.init.save_recovery_stub", lambda **kwargs: captured_stub.update(kwargs))

    result = init_module.run_init(
        repo_root=repo_root,
        repo_id_override=None,
        host_mode="auto",
        skip_model_download=False,
    )

    assert result.outcome == init_module.INIT_OUTCOME_BLOCKED_CONFIG_CORRUPT
    assert "Unable to recover" in result.lines[0]
    assert any(str(preserved) in line for line in result.lines)
    assert captured_stub == {
        "current_step": "config_recovery",
        "last_error": "corrupt toml",
    }


def test_run_init_should_report_repaired_when_fixing_existing_machine_state(tmp_path: Path, monkeypatch) -> None:
    """init should create a backup first and report repaired when bootstrap state needs repair."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_root = tmp_path / "home"
    backup_calls: list[str] = []

    initial_config = _machine_config(bootstrap_state="repair_needed")
    ready_config = _machine_config(bootstrap_state="provisioning", readiness_state="ready", last_error=None)
    registration = RepoRegistration(
        repo_state_version=1,
        repo_id="github.com/example/repo",
        identity_strength="git_remote",
        git_root=str(repo_root),
        source_remote="origin",
        registered_at="2026-03-19T00:00:00+00:00",
        machine_instance_id=initial_config.machine_instance_id,
        claude_status="not_checked",
    )

    monkeypatch.setattr(init_module, "get_shellbrain_home", lambda: home_root)
    monkeypatch.setattr(init_module, "_acquire_init_lock", lambda: nullcontext())
    monkeypatch.setattr(init_module, "_ensure_dependencies", lambda: None)
    monkeypatch.setattr(init_module, "try_load_machine_config", lambda: (initial_config, None))
    monkeypatch.setattr(init_module, "save_machine_config", lambda config: None)
    monkeypatch.setattr(init_module, "_migrate_machine_config", lambda config: config)
    monkeypatch.setattr(init_module, "_ensure_managed_container", lambda config: False)
    monkeypatch.setattr(init_module, "_backup_before_repair", lambda config: backup_calls.append(config.machine_instance_id))
    monkeypatch.setattr(init_module, "_wait_for_postgres", lambda admin_dsn: None)
    monkeypatch.setattr(init_module, "_reconcile_database", lambda config: False)
    monkeypatch.setattr(init_module, "_prewarm_embeddings", lambda config, skip_model_download: (True, ready_config))
    monkeypatch.setattr(init_module, "_register_repo", lambda **kwargs: (registration, True))
    monkeypatch.setattr(init_module, "_handle_claude_integration", lambda **kwargs: None)

    result = init_module.run_init(
        repo_root=repo_root,
        repo_id_override=None,
        host_mode="auto",
        skip_model_download=False,
    )

    assert result.outcome == init_module.INIT_OUTCOME_REPAIRED
    assert backup_calls == [initial_config.machine_instance_id]
    assert any("Managed instance:" in line for line in result.lines)
    assert any("Repo: github.com/example/repo" == line for line in result.lines)


def test_handle_claude_integration_should_noop_with_repo_signal_only(tmp_path: Path, monkeypatch) -> None:
    """auto Claude handling should not mutate config when only repo-local Claude files are present."""

    repo_root = tmp_path / "claude-repo"
    (repo_root / ".claude").mkdir(parents=True)
    registration = RepoRegistration(
        repo_state_version=1,
        repo_id="github.com/example/repo",
        identity_strength="git_remote",
        git_root=str(repo_root),
        source_remote="origin",
        registered_at="2026-03-19T00:00:00+00:00",
        machine_instance_id="inst-1",
        claude_status="not_checked",
    )

    monkeypatch.setattr(init_module, "detect_claude_runtime_without_hook", lambda: False)

    note = init_module._handle_claude_integration(repo_root=repo_root, registration=registration, host_mode="auto")

    assert note == "Claude repo detected but no active Claude runtime was found. Rerun from Claude Code or pass --host claude to install the Shellbrain hook."


def test_handle_claude_integration_should_install_when_forced(tmp_path: Path, monkeypatch) -> None:
    """forced Claude mode should install the hook even without runtime auto-detection."""

    repo_root = tmp_path / "claude-repo"
    repo_root.mkdir()
    registration = RepoRegistration(
        repo_state_version=1,
        repo_id="github.com/example/repo",
        identity_strength="git_remote",
        git_root=str(repo_root),
        source_remote="origin",
        registered_at="2026-03-19T00:00:00+00:00",
        machine_instance_id="inst-1",
        claude_status="not_checked",
    )
    installed: list[Path] = []

    monkeypatch.setattr(init_module, "detect_claude_runtime_without_hook", lambda: False)
    monkeypatch.setattr(
        init_module,
        "install_claude_hook",
        lambda *, repo_root: installed.append(repo_root) or repo_root / ".claude" / "settings.local.json",
    )

    note = init_module._handle_claude_integration(repo_root=repo_root, registration=registration, host_mode="claude")

    assert installed == [repo_root]
    assert note == f"Installed Claude hook at {repo_root / '.claude' / 'settings.local.json'}"


def _machine_config(*, bootstrap_state: str, readiness_state: str = "pending", last_error: str | None = "repair me") -> MachineConfig:
    """Return one minimal machine config for init tests."""

    return MachineConfig(
        config_version=1,
        bootstrap_version=1,
        runtime_mode="managed_local",
        bootstrap_state=bootstrap_state,
        current_step="bootstrap",
        last_error=last_error,
        database=DatabaseState(
            app_dsn="postgresql+psycopg://shellbrain_app:app@127.0.0.1:55432/shellbrain",
            admin_dsn="postgresql+psycopg://shellbrain_admin:admin@127.0.0.1:55432/shellbrain",
        ),
        managed=ManagedInstanceState(
            instance_id="inst-1",
            container_name="shellbrain-postgres-test",
            image="pgvector/pgvector:pg16",
            host="127.0.0.1",
            port=55432,
            db_name="shellbrain",
            data_dir="/tmp/shellbrain-data",
            admin_user="shellbrain_admin",
            admin_password="admin-secret",
            app_user="shellbrain_app",
            app_password="app-secret",
        ),
        backups=BackupState(root="/tmp/shellbrain-backups"),
        embeddings=EmbeddingRuntimeState(
            provider="sentence_transformers",
            model="all-MiniLM-L6-v2",
            model_revision=None,
            backend_version="1.0.0",
            cache_path="/tmp/shellbrain-models",
            readiness_state=readiness_state,
            last_error=last_error,
        ),
    )
