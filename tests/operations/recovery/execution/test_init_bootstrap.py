"""Bootstrap and repair contracts for the managed init flow."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

import app.startup.runtime_admin as init_module
from app.core.entities.machine_config import (
    BackupState,
    DatabaseState,
    EmbeddingRuntimeState,
    MachineConfig,
    ManagedInstanceState,
)
from app.infrastructure.db.admin.provisioning import managed_local as managed_runtime
from app.infrastructure.local_state.repo_registration_store import RepoRegistration
from app.entrypoints.cli.presenters.init import render_success_lines as render_init_lines


@pytest.fixture(autouse=True)
def _isolate_machine_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Prevent init failure paths from mutating the real machine config."""

    monkeypatch.setenv("SHELLBRAIN_HOME", str(tmp_path / "shellbrain-home"))


def _render_success_lines(**kwargs) -> list[str]:
    """Render init success lines through the CLI presenter."""

    return render_init_lines(**kwargs, **init_module.init_success_presenter_context())


def test_run_init_should_block_when_corrupt_config_cannot_be_recovered(
    tmp_path: Path, monkeypatch
) -> None:
    """init should stop with blocked_config_corrupt when corrupt machine state cannot be rediscovered."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_root = tmp_path / "home"
    preserved = home_root / "config.corrupt.20260319T000000Z.toml"
    captured_stub: dict[str, str | None] = {}

    monkeypatch.setattr(init_module, "get_shellbrain_home", lambda: home_root)
    monkeypatch.setattr(init_module, "acquire_init_lock", lambda: nullcontext())
    monkeypatch.setattr(init_module, "_ensure_dependencies", lambda: None)
    monkeypatch.setattr(
        init_module, "try_load_machine_config", lambda: (None, "corrupt toml")
    )
    monkeypatch.setattr(init_module, "backup_corrupt_machine_config", lambda: preserved)
    monkeypatch.setattr(
        init_module, "_recover_machine_config", lambda: None
    )
    monkeypatch.setattr(
        "app.startup.runtime_admin.save_recovery_stub",
        lambda **kwargs: captured_stub.update(kwargs),
    )

    result = init_module.run_init(
        repo_root=repo_root,
        repo_id_override=None,
        register_repo_now=True,
        skip_model_download=False,
        skip_host_assets=True,
        render_success_lines=_render_success_lines,
    )

    assert result.outcome == init_module.INIT_OUTCOME_BLOCKED_CONFIG_CORRUPT
    assert "Unable to recover" in result.lines[0]
    assert any(str(preserved) in line for line in result.lines)
    assert captured_stub == {
        "current_step": "config_recovery",
        "last_error": "corrupt toml",
    }


def test_run_init_should_report_repaired_when_fixing_existing_machine_state(
    tmp_path: Path, monkeypatch
) -> None:
    """init should create a backup first and report repaired when bootstrap state needs repair."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_root = tmp_path / "home"
    backup_calls: list[str] = []

    initial_config = _machine_config(bootstrap_state="repair_needed")
    ready_config = _machine_config(
        bootstrap_state="provisioning", readiness_state="ready", last_error=None
    )
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
    monkeypatch.setattr(init_module, "acquire_init_lock", lambda: nullcontext())
    monkeypatch.setattr(init_module, "_ensure_dependencies", lambda: None)
    monkeypatch.setattr(
        init_module, "try_load_machine_config", lambda: (initial_config, None)
    )
    monkeypatch.setattr(init_module, "save_machine_config", lambda config: None)
    monkeypatch.setattr(init_module, "_migrate_machine_config", lambda config: config)
    monkeypatch.setattr(init_module, "_ensure_managed_dependencies", lambda: None)
    monkeypatch.setattr(init_module, "_ensure_managed_container", lambda config: False)
    monkeypatch.setattr(
        init_module,
        "_backup_before_repair",
        lambda config: backup_calls.append(config.machine_instance_id),
    )
    monkeypatch.setattr(init_module, "wait_for_postgres", lambda admin_dsn: None)
    monkeypatch.setattr(
        init_module, "_reconcile_database", lambda config: (False, config)
    )
    monkeypatch.setattr(init_module, "_apply_schema_migrations", lambda config: True)
    monkeypatch.setattr(
        init_module,
        "prewarm_embeddings",
        lambda config, skip_model_download: (True, ready_config),
    )
    monkeypatch.setattr(
        init_module, "_register_repo", lambda **kwargs: (registration, True)
    )

    result = init_module.run_init(
        repo_root=repo_root,
        repo_id_override=None,
        register_repo_now=True,
        skip_model_download=False,
        skip_host_assets=True,
        render_success_lines=_render_success_lines,
    )

    assert result.outcome == init_module.INIT_OUTCOME_REPAIRED
    assert backup_calls == [initial_config.machine_instance_id]
    assert any("Managed instance:" in line for line in result.lines)
    assert any("Repo: github.com/example/repo" == line for line in result.lines)


def test_run_init_should_mark_repair_needed_when_blocked_by_conflict(
    tmp_path: Path, monkeypatch
) -> None:
    """blocked conflicts should not leave machine state stranded in provisioning."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_root = tmp_path / "home"
    initial_config = _machine_config(bootstrap_state="provisioning", last_error=None)
    marked: list[str] = []

    monkeypatch.setattr(init_module, "get_shellbrain_home", lambda: home_root)
    monkeypatch.setattr(init_module, "acquire_init_lock", lambda: nullcontext())
    monkeypatch.setattr(init_module, "_ensure_dependencies", lambda: None)
    monkeypatch.setattr(
        init_module, "try_load_machine_config", lambda: (initial_config, None)
    )
    monkeypatch.setattr(init_module, "save_machine_config", lambda config: None)
    monkeypatch.setattr(init_module, "_migrate_machine_config", lambda config: config)
    monkeypatch.setattr(init_module, "_ensure_managed_dependencies", lambda: None)
    monkeypatch.setattr(
        init_module,
        "_ensure_managed_container",
        lambda config: (_ for _ in ()).throw(
            init_module.InitConflictError("managed port already claimed")
        ),
    )
    monkeypatch.setattr(
        init_module, "_mark_repair_needed", lambda message: marked.append(message)
    )

    result = init_module.run_init(
        repo_root=repo_root,
        repo_id_override=None,
        register_repo_now=True,
        skip_model_download=False,
        skip_host_assets=True,
        render_success_lines=_render_success_lines,
    )

    assert result.outcome == init_module.INIT_OUTCOME_BLOCKED_CONFLICT
    assert result.lines == ["managed port already claimed"]
    assert marked == ["managed port already claimed"]


def test_run_init_should_block_cleanly_when_installed_package_is_older_than_database_revision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """init should report one blocked conflict instead of leaking an Alembic traceback on schema-version mismatch."""

    from app.startup.migrations import DatabaseMigrationConflictError

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_root = tmp_path / "home"
    initial_config = _machine_config(bootstrap_state="provisioning", last_error=None)
    marked: list[str] = []

    monkeypatch.setattr(init_module, "get_shellbrain_home", lambda: home_root)
    monkeypatch.setattr(init_module, "acquire_init_lock", lambda: nullcontext())
    monkeypatch.setattr(init_module, "_ensure_dependencies", lambda: None)
    monkeypatch.setattr(
        init_module, "try_load_machine_config", lambda: (initial_config, None)
    )
    monkeypatch.setattr(init_module, "save_machine_config", lambda config: None)
    monkeypatch.setattr(init_module, "_migrate_machine_config", lambda config: config)
    monkeypatch.setattr(init_module, "_ensure_managed_dependencies", lambda: None)
    monkeypatch.setattr(init_module, "_ensure_managed_container", lambda config: False)
    monkeypatch.setattr(init_module, "wait_for_postgres", lambda admin_dsn: None)
    monkeypatch.setattr(
        init_module, "_reconcile_database", lambda config: (False, config)
    )
    monkeypatch.setattr(
        "app.startup.migrations.upgrade_database_for_config",
        lambda config: (_ for _ in ()).throw(
            DatabaseMigrationConflictError(
                "Installed Shellbrain package (0.1.22) cannot manage database revision 20260415_0012."
            )
        ),
    )
    monkeypatch.setattr(
        init_module, "_mark_repair_needed", lambda message: marked.append(message)
    )

    result = init_module.run_init(
        repo_root=repo_root,
        repo_id_override=None,
        register_repo_now=False,
        skip_model_download=False,
        skip_host_assets=True,
        render_success_lines=_render_success_lines,
    )

    assert result.outcome == init_module.INIT_OUTCOME_BLOCKED_CONFLICT
    assert result.lines == [
        "Installed Shellbrain package (0.1.22) cannot manage database revision 20260415_0012."
    ]
    assert marked == [
        "Installed Shellbrain package (0.1.22) cannot manage database revision 20260415_0012."
    ]


def test_run_init_should_defer_repo_registration_outside_any_repo(
    tmp_path: Path, monkeypatch
) -> None:
    """plain init should succeed outside a repo and defer repo registration until first use."""

    repo_root = tmp_path / "not-a-repo"
    repo_root.mkdir()
    home_root = tmp_path / "home"
    initial_config = _machine_config(bootstrap_state="provisioning")
    ready_config = _machine_config(
        bootstrap_state="provisioning", readiness_state="ready", last_error=None
    )
    register_calls: list[dict[str, object]] = []

    monkeypatch.setattr(init_module, "get_shellbrain_home", lambda: home_root)
    monkeypatch.setattr(init_module, "acquire_init_lock", lambda: nullcontext())
    monkeypatch.setattr(init_module, "_ensure_dependencies", lambda: None)
    monkeypatch.setattr(
        init_module, "try_load_machine_config", lambda: (initial_config, None)
    )
    monkeypatch.setattr(init_module, "save_machine_config", lambda config: None)
    monkeypatch.setattr(init_module, "_migrate_machine_config", lambda config: config)
    monkeypatch.setattr(init_module, "_ensure_managed_dependencies", lambda: None)
    monkeypatch.setattr(init_module, "_ensure_managed_container", lambda config: False)
    monkeypatch.setattr(init_module, "wait_for_postgres", lambda admin_dsn: None)
    monkeypatch.setattr(
        init_module, "_reconcile_database", lambda config: (False, config)
    )
    monkeypatch.setattr(init_module, "_apply_schema_migrations", lambda config: False)
    monkeypatch.setattr(
        init_module,
        "prewarm_embeddings",
        lambda config, skip_model_download: (True, ready_config),
    )
    monkeypatch.setattr(
        init_module, "_register_repo", lambda **kwargs: register_calls.append(kwargs)
    )

    result = init_module.run_init(
        repo_root=repo_root,
        repo_id_override=None,
        register_repo_now=False,
        skip_model_download=False,
        skip_host_assets=True,
        render_success_lines=_render_success_lines,
    )

    assert result.outcome == init_module.INIT_OUTCOME_INITIALIZED
    assert register_calls == []
    assert (
        "Repo registration: deferred until first Shellbrain use inside a repo."
        in result.lines
    )


def test_run_init_should_apply_schema_migrations_after_database_reconcile(
    tmp_path: Path, monkeypatch
) -> None:
    """init should migrate the Shellbrain schema before continuing to embeddings."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_root = tmp_path / "home"
    initial_config = _machine_config(bootstrap_state="provisioning")
    ready_config = _machine_config(
        bootstrap_state="provisioning", readiness_state="ready", last_error=None
    )
    call_order: list[str] = []

    monkeypatch.setattr(init_module, "get_shellbrain_home", lambda: home_root)
    monkeypatch.setattr(init_module, "acquire_init_lock", lambda: nullcontext())
    monkeypatch.setattr(init_module, "_ensure_dependencies", lambda: None)
    monkeypatch.setattr(
        init_module, "try_load_machine_config", lambda: (initial_config, None)
    )
    monkeypatch.setattr(init_module, "save_machine_config", lambda config: None)
    monkeypatch.setattr(init_module, "_migrate_machine_config", lambda config: config)
    monkeypatch.setattr(init_module, "_ensure_managed_dependencies", lambda: None)
    monkeypatch.setattr(init_module, "_ensure_managed_container", lambda config: False)
    monkeypatch.setattr(init_module, "wait_for_postgres", lambda admin_dsn: None)
    monkeypatch.setattr(
        init_module,
        "_reconcile_database",
        lambda config: (call_order.append("reconcile") or False, config),
    )
    monkeypatch.setattr(
        init_module,
        "_apply_schema_migrations",
        lambda config: call_order.append("migrate") or True,
    )
    monkeypatch.setattr(
        init_module,
        "prewarm_embeddings",
        lambda config, skip_model_download: (
            call_order.append("embeddings") or True,
            ready_config,
        ),
    )
    monkeypatch.setattr(
        init_module,
        "_register_repo",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected repo registration")
        ),
    )

    result = init_module.run_init(
        repo_root=repo_root,
        repo_id_override=None,
        register_repo_now=False,
        skip_model_download=False,
        skip_host_assets=True,
        render_success_lines=_render_success_lines,
    )

    assert result.outcome == init_module.INIT_OUTCOME_INITIALIZED
    assert call_order == ["reconcile", "migrate", "embeddings"]


def test_run_init_should_run_maintenance_when_machine_already_ready(
    tmp_path: Path, monkeypatch
) -> None:
    """ready init should refresh runtime maintenance without re-bootstrap side effects."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_root = tmp_path / "home"
    ready_config = _machine_config(
        bootstrap_state="ready", readiness_state="ready", last_error=None
    )
    call_order: list[str] = []

    monkeypatch.setattr(init_module, "get_shellbrain_home", lambda: home_root)
    monkeypatch.setattr(init_module, "acquire_init_lock", lambda: nullcontext())
    monkeypatch.setattr(init_module, "_ensure_dependencies", lambda: None)
    monkeypatch.setattr(
        init_module, "try_load_machine_config", lambda: (ready_config, None)
    )
    monkeypatch.setattr(
        init_module, "load_repo_registration_for_target", lambda repo_root: None
    )
    monkeypatch.setattr(
        init_module,
        "resolve_storage_selection",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("ready maintenance should not ask storage questions")
        ),
    )
    monkeypatch.setattr(init_module, "save_machine_config", lambda config: None)
    monkeypatch.setattr(
        init_module,
        "_migrate_machine_config",
        lambda config: call_order.append("config") or config,
    )
    monkeypatch.setattr(
        init_module,
        "_ensure_managed_dependencies",
        lambda: call_order.append("managed_deps"),
    )
    monkeypatch.setattr(
        init_module,
        "_ensure_managed_container",
        lambda config: call_order.append("container") or False,
    )
    monkeypatch.setattr(
        init_module,
        "wait_for_postgres",
        lambda admin_dsn: call_order.append("wait"),
    )
    monkeypatch.setattr(
        init_module,
        "_reconcile_database",
        lambda config: (call_order.append("reconcile") or False, config),
    )
    monkeypatch.setattr(
        init_module,
        "_apply_schema_migrations",
        lambda config: call_order.append("migrate") or True,
    )
    monkeypatch.setattr(
        init_module,
        "prewarm_embeddings",
        lambda config, skip_model_download: (_ for _ in ()).throw(
            AssertionError("ready maintenance should not prewarm embeddings")
        ),
    )
    monkeypatch.setattr(
        init_module,
        "_register_repo",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("ready maintenance should not register repos")
        ),
    )
    monkeypatch.setattr(
        init_module,
        "install_host_assets",
        lambda host_mode, force: (
            call_order.append("assets") or _FakeHostAssetsResult()
        ),
    )

    result = init_module.run_init(
        repo_root=repo_root,
        repo_id_override=None,
        register_repo_now=True,
        skip_model_download=False,
        skip_host_assets=False,
        render_success_lines=_render_success_lines,
    )

    assert result.outcome == init_module.INIT_OUTCOME_INITIALIZED
    assert result.exit_code == 0
    assert call_order == [
        "config",
        "managed_deps",
        "container",
        "wait",
        "reconcile",
        "migrate",
        "assets",
    ]


def test_ready_external_init_should_run_maintenance_without_docker(
    tmp_path: Path, monkeypatch
) -> None:
    """ready external-postgres init should migrate the DB without managed Docker setup."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_root = tmp_path / "home"
    ready_config = _external_machine_config(
        bootstrap_state="ready", readiness_state="ready", last_error=None
    )
    call_order: list[str] = []

    monkeypatch.setattr(init_module, "get_shellbrain_home", lambda: home_root)
    monkeypatch.setattr(init_module, "acquire_init_lock", lambda: nullcontext())
    monkeypatch.setattr(init_module, "_ensure_dependencies", lambda: None)
    monkeypatch.setattr(
        init_module, "try_load_machine_config", lambda: (ready_config, None)
    )
    monkeypatch.setattr(
        init_module, "load_repo_registration_for_target", lambda repo_root: None
    )
    monkeypatch.setattr(
        init_module,
        "resolve_storage_selection",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("ready maintenance should not ask storage questions")
        ),
    )
    monkeypatch.setattr(init_module, "save_machine_config", lambda config: None)
    monkeypatch.setattr(
        init_module,
        "_migrate_machine_config",
        lambda config: call_order.append("config") or config,
    )
    monkeypatch.setattr(
        init_module,
        "_ensure_managed_dependencies",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected docker check")),
    )
    monkeypatch.setattr(
        init_module,
        "_ensure_managed_container",
        lambda config: (_ for _ in ()).throw(
            AssertionError("unexpected managed container step")
        ),
    )
    monkeypatch.setattr(
        init_module,
        "wait_for_postgres",
        lambda admin_dsn: call_order.append("wait"),
    )
    monkeypatch.setattr(
        init_module,
        "_reconcile_database",
        lambda config: (call_order.append("reconcile") or False, config),
    )
    monkeypatch.setattr(
        init_module,
        "_apply_schema_migrations",
        lambda config: call_order.append("migrate") or False,
    )
    monkeypatch.setattr(
        init_module,
        "prewarm_embeddings",
        lambda config, skip_model_download: (_ for _ in ()).throw(
            AssertionError("ready maintenance should not prewarm embeddings")
        ),
    )
    monkeypatch.setattr(
        init_module,
        "_register_repo",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("ready maintenance should not register repos")
        ),
    )

    result = init_module.run_init(
        repo_root=repo_root,
        repo_id_override=None,
        register_repo_now=True,
        skip_model_download=False,
        skip_host_assets=True,
        render_success_lines=_render_success_lines,
    )

    assert result.outcome == init_module.INIT_OUTCOME_NOOP
    assert call_order == ["config", "wait", "reconcile", "migrate"]


def test_ready_init_should_propagate_schema_migration_failure(
    tmp_path: Path, monkeypatch
) -> None:
    """ready maintenance should fail closed when packaged DB migrations fail."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_root = tmp_path / "home"
    ready_config = _machine_config(
        bootstrap_state="ready", readiness_state="ready", last_error=None
    )
    marked: list[str] = []

    monkeypatch.setattr(init_module, "get_shellbrain_home", lambda: home_root)
    monkeypatch.setattr(init_module, "acquire_init_lock", lambda: nullcontext())
    monkeypatch.setattr(init_module, "_ensure_dependencies", lambda: None)
    monkeypatch.setattr(
        init_module, "try_load_machine_config", lambda: (ready_config, None)
    )
    monkeypatch.setattr(
        init_module, "load_repo_registration_for_target", lambda repo_root: None
    )
    monkeypatch.setattr(init_module, "save_machine_config", lambda config: None)
    monkeypatch.setattr(init_module, "_migrate_machine_config", lambda config: config)
    monkeypatch.setattr(init_module, "_ensure_managed_dependencies", lambda: None)
    monkeypatch.setattr(init_module, "_ensure_managed_container", lambda config: False)
    monkeypatch.setattr(init_module, "wait_for_postgres", lambda admin_dsn: None)
    monkeypatch.setattr(
        init_module, "_reconcile_database", lambda config: (False, config)
    )
    monkeypatch.setattr(
        init_module,
        "_apply_schema_migrations",
        lambda config: (_ for _ in ()).throw(
            init_module.InitConflictError("schema migration failed")
        ),
    )
    monkeypatch.setattr(
        init_module, "_mark_repair_needed", lambda message: marked.append(message)
    )

    result = init_module.run_init(
        repo_root=repo_root,
        repo_id_override=None,
        register_repo_now=True,
        skip_model_download=False,
        skip_host_assets=False,
        render_success_lines=_render_success_lines,
    )

    assert result.outcome == init_module.INIT_OUTCOME_BLOCKED_CONFLICT
    assert result.exit_code == 10
    assert result.lines == ["schema migration failed"]
    assert marked == ["schema migration failed"]


def test_external_init_should_skip_managed_container_setup(
    monkeypatch, tmp_path: Path
) -> None:
    """external init should not require Docker-backed managed runtime helpers."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    home_root = tmp_path / "home"
    initial_config = _external_machine_config(bootstrap_state="provisioning")
    ready_config = _external_machine_config(
        bootstrap_state="provisioning", readiness_state="ready", last_error=None
    )
    saved: list[MachineConfig] = []

    monkeypatch.setattr(init_module, "get_shellbrain_home", lambda: home_root)
    monkeypatch.setattr(init_module, "acquire_init_lock", lambda: nullcontext())
    monkeypatch.setattr(init_module, "_ensure_dependencies", lambda: None)
    monkeypatch.setattr(init_module, "try_load_machine_config", lambda: (None, None))
    monkeypatch.setattr(
        init_module,
        "_ensure_managed_dependencies",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected docker check")),
    )
    monkeypatch.setattr(
        init_module.external_runtime,
        "build_fresh_machine_config",
        lambda admin_dsn: initial_config,
    )
    monkeypatch.setattr(
        init_module, "save_machine_config", lambda config: saved.append(config)
    )
    monkeypatch.setattr(init_module, "_migrate_machine_config", lambda config: config)
    monkeypatch.setattr(
        init_module,
        "_ensure_managed_container",
        lambda config: (_ for _ in ()).throw(
            AssertionError("unexpected managed container step")
        ),
    )
    monkeypatch.setattr(init_module, "wait_for_postgres", lambda admin_dsn: None)
    monkeypatch.setattr(
        init_module, "_reconcile_database", lambda config: (False, config)
    )
    monkeypatch.setattr(init_module, "_apply_schema_migrations", lambda config: False)
    monkeypatch.setattr(
        init_module,
        "prewarm_embeddings",
        lambda config, skip_model_download: (True, ready_config),
    )
    monkeypatch.setattr(
        init_module,
        "_register_repo",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("unexpected repo registration")
        ),
    )

    result = init_module.run_init(
        repo_root=repo_root,
        repo_id_override=None,
        register_repo_now=False,
        skip_model_download=False,
        skip_host_assets=True,
        render_success_lines=_render_success_lines,
        storage="external",
        admin_dsn=initial_config.database.admin_dsn,
    )

    assert result.outcome == init_module.INIT_OUTCOME_INITIALIZED
    assert any("External database:" in line for line in result.lines)
    assert saved[0].runtime_mode == "external_postgres"


def test_ensure_managed_runtime_ready_should_start_managed_container_and_wait(
    monkeypatch,
) -> None:
    """operation readiness should start the configured managed runtime once."""

    config = _machine_config(bootstrap_state="ready")
    calls: list[object] = []

    monkeypatch.setattr(init_module, "try_load_machine_config", lambda: (config, None))
    monkeypatch.setattr(
        init_module, "ensure_managed_runtime_available", lambda: calls.append("deps")
    )
    monkeypatch.setattr(
        init_module.managed_runtime,
        "ensure_existing_managed_container_running",
        lambda received: calls.append(("container", received)) or True,
    )
    monkeypatch.setattr(
        init_module,
        "wait_for_postgres",
        lambda dsn, timeout_seconds: calls.append(("wait", dsn, timeout_seconds)),
    )

    init_module.ensure_managed_runtime_ready()

    assert calls == [
        "deps",
        ("container", config),
        ("wait", config.database.admin_dsn, 15),
    ]


@pytest.mark.parametrize(
    "loaded_factory",
    [
        lambda: (None, None),
        lambda: (None, "corrupt config"),
        lambda: (_external_machine_config(bootstrap_state="ready"), None),
    ],
)
def test_ensure_managed_runtime_ready_should_skip_without_managed_config(
    monkeypatch, loaded_factory
) -> None:
    """operation readiness should leave missing, corrupt, and external configs alone."""

    monkeypatch.setattr(init_module, "try_load_machine_config", loaded_factory)
    monkeypatch.setattr(
        init_module,
        "ensure_managed_runtime_available",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected docker check")),
    )

    init_module.ensure_managed_runtime_ready()


def test_reconcile_database_should_inline_role_password_literals(monkeypatch) -> None:
    """role creation should not use server-side bind params inside CREATE/ALTER ROLE."""

    config = _machine_config(bootstrap_state="provisioning")
    postgres_cursor = _FakeCursor(fetch_results=[(1,)])
    admin_cursor = _FakeCursor(fetch_results=[None])
    connections = [_FakeConnection(postgres_cursor), _FakeConnection(admin_cursor)]

    monkeypatch.setattr(
        managed_runtime.psycopg, "connect", lambda *args, **kwargs: connections.pop(0)
    )
    monkeypatch.setattr(
        managed_runtime, "reconcile_app_role_privileges", lambda **kwargs: None
    )
    monkeypatch.setattr(
        managed_runtime, "ensure_instance_metadata", lambda *args, **kwargs: None
    )

    changed = managed_runtime.reconcile_database(config)

    assert changed is True
    create_role_call = admin_cursor.calls[1]
    assert create_role_call[1] is None


def test_ensure_existing_managed_container_running_should_start_stopped_owned_container(
    monkeypatch,
) -> None:
    """operation readiness should start only the configured owned container."""

    config = _machine_config(bootstrap_state="ready")
    started: list[str] = []

    monkeypatch.setattr(managed_runtime, "_home_hash", lambda: "homehash")
    monkeypatch.setattr(
        managed_runtime,
        "inspect_container",
        lambda name: _container_info(config, running=False),
    )
    monkeypatch.setattr(
        managed_runtime, "_start_container", lambda name: started.append(name)
    )

    changed = managed_runtime.ensure_existing_managed_container_running(config)

    assert changed is True
    assert started == [config.managed.container_name]


def test_ensure_existing_managed_container_running_should_noop_for_running_owned_container(
    monkeypatch,
) -> None:
    """operation readiness should not restart an already-running owned container."""

    config = _machine_config(bootstrap_state="ready")

    monkeypatch.setattr(managed_runtime, "_home_hash", lambda: "homehash")
    monkeypatch.setattr(
        managed_runtime,
        "inspect_container",
        lambda name: _container_info(config, running=True),
    )
    monkeypatch.setattr(
        managed_runtime,
        "_start_container",
        lambda name: (_ for _ in ()).throw(AssertionError("unexpected start")),
    )

    assert managed_runtime.ensure_existing_managed_container_running(config) is False


@pytest.mark.parametrize(
    ("info", "message"),
    [
        (None, "does not exist"),
        (
            {
                "Config": {"Labels": {managed_runtime.MANAGED_LABEL: "false"}},
                "State": {"Running": False},
            },
            "not owned",
        ),
        (
            {
                "Config": {
                    "Labels": {
                        managed_runtime.MANAGED_LABEL: "true",
                        managed_runtime.MANAGED_HOME_LABEL: "homehash",
                        managed_runtime.MANAGED_INSTANCE_LABEL: "other",
                    }
                },
                "State": {"Running": False},
            },
            "does not match",
        ),
    ],
)
def test_ensure_existing_managed_container_running_should_refuse_unsafe_targets(
    monkeypatch, info, message: str
) -> None:
    """operation readiness should not create or adopt unsafe containers."""

    config = _machine_config(bootstrap_state="ready")

    monkeypatch.setattr(managed_runtime, "_home_hash", lambda: "homehash")
    monkeypatch.setattr(managed_runtime, "inspect_container", lambda name: info)
    monkeypatch.setattr(
        managed_runtime,
        "_start_container",
        lambda name: (_ for _ in ()).throw(AssertionError("unexpected start")),
    )

    with pytest.raises(init_module.InitConflictError, match=message):
        managed_runtime.ensure_existing_managed_container_running(config)


def test_create_managed_container_should_enable_docker_restart_policy(
    monkeypatch, tmp_path: Path
) -> None:
    """new managed containers should restart after Docker restarts."""

    config = _machine_config(bootstrap_state="provisioning", data_dir=str(tmp_path))
    commands: list[list[str]] = []

    class _Completed:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(
        managed_runtime.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command) or _Completed(),
    )

    managed_runtime._create_managed_container(config)

    command = commands[0]
    restart_index = command.index("--restart")
    assert command[restart_index + 1] == "unless-stopped"


def test_select_managed_port_should_skip_ports_claimed_by_created_containers(
    monkeypatch,
) -> None:
    """created containers should reserve their declared host ports for future init runs."""

    class _Socket:
        def setsockopt(self, *args, **kwargs):
            return None

        def bind(self, address):
            host, port = address
            if port != 55433:
                raise OSError("port unavailable")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(managed_runtime, "_managed_claimed_host_ports", lambda: {55432})
    monkeypatch.setattr(
        managed_runtime.socket, "socket", lambda *args, **kwargs: _Socket()
    )

    selected = managed_runtime._select_managed_port()

    assert selected == 55433


def _machine_config(
    *,
    bootstrap_state: str,
    readiness_state: str = "pending",
    last_error: str | None = "repair me",
    data_dir: str = "/tmp/shellbrain-data",
) -> MachineConfig:
    """Return one minimal machine config for init tests."""

    return MachineConfig(
        config_version=2,
        bootstrap_version=1,
        instance_id="inst-1",
        runtime_mode="managed_local",
        bootstrap_state=bootstrap_state,
        current_step="bootstrap",
        last_error=last_error,
        database=DatabaseState(
            app_dsn="postgresql+psycopg://app_user:app_password@127.0.0.1:55432/shellbrain",
            admin_dsn="postgresql+psycopg://admin_user:admin_password@127.0.0.1:55432/shellbrain",
        ),
        managed=ManagedInstanceState(
            instance_id="inst-1",
            container_name="shellbrain-postgres-test",
            image="pgvector/pgvector:pg16",
            host="127.0.0.1",
            port=55432,
            db_name="shellbrain",
            data_dir=data_dir,
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


def _container_info(config: MachineConfig, *, running: bool) -> dict[str, object]:
    """Return Docker inspect data for the configured managed container."""

    return {
        "Config": {
            "Labels": {
                managed_runtime.MANAGED_LABEL: "true",
                managed_runtime.MANAGED_HOME_LABEL: "homehash",
                managed_runtime.MANAGED_INSTANCE_LABEL: config.machine_instance_id,
            }
        },
        "State": {"Running": running},
    }


def _external_machine_config(
    *,
    bootstrap_state: str,
    readiness_state: str = "pending",
    last_error: str | None = "repair me",
) -> MachineConfig:
    """Return one minimal external machine config for init tests."""

    return MachineConfig(
        config_version=2,
        bootstrap_version=1,
        instance_id="ext-1",
        runtime_mode="external_postgres",
        bootstrap_state=bootstrap_state,
        current_step="bootstrap",
        last_error=last_error,
        database=DatabaseState(
            app_dsn="postgresql+psycopg://shellbrain_app:app_password@db.example.com:5432/shellbrain",
            admin_dsn="postgresql+psycopg://admin_user:admin_password@db.example.com:5432/shellbrain",
        ),
        managed=None,
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


class _FakeHostAssetsResult:
    """Stub for HostAssetInstallResult."""

    lines: list[str] = []


class _FakeCursor:
    """Minimal cursor stub for init unit tests."""

    def __init__(self, *, fetch_results: list[object | None]) -> None:
        self._fetch_results = list(fetch_results)
        self.calls: list[tuple[object, object | None]] = []

    def execute(self, query, params=None) -> None:
        self.calls.append((query, params))

    def fetchone(self):
        if self._fetch_results:
            return self._fetch_results.pop(0)
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeConnection:
    """Minimal connection stub for init unit tests."""

    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False
