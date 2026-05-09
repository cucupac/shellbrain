"""Shellbrain machine bootstrap and repair flow."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Callable

from app.infrastructure.local_state.init_lock import acquire_init_lock
from app.infrastructure.local_state.paths import get_shellbrain_home
from app.infrastructure.runtime import external_runtime, managed_runtime
from app.infrastructure.runtime.init_admin import (
    ensure_managed_runtime_available,
    recover_managed_machine_config,
)
from app.infrastructure.db.admin.connection import wait_for_postgres
from app.infrastructure.db.admin.destructive_guard import (
    backup_and_verify_before_destructive_action,
)
from app.infrastructure.runtime.embedding_prewarm import prewarm_embeddings
from app.core.entities.admin_errors import InitConflictError, InitDependencyError
from app.core.use_cases.admin.initialize_runtime import (
    INIT_OUTCOME_BLOCKED_CONFIG_CORRUPT,
    INIT_OUTCOME_BLOCKED_CONFLICT,
    INIT_OUTCOME_BLOCKED_DEPENDENCY,
    INIT_OUTCOME_BLOCKED_LOCK,
    INIT_OUTCOME_INITIALIZED,
    INIT_OUTCOME_NOOP,
    INIT_OUTCOME_REPAIRED,
    InitResult,
    InitializeRuntimePorts,
    run_initialize_runtime,
)
from app.startup.config import get_config_provider
from app.infrastructure.db.admin.instance_guard import fingerprint_summary
from app.infrastructure.local_state.machine_config_store import (
    BOOTSTRAP_STATE_PROVISIONING,
    BOOTSTRAP_STATE_READY,
    BOOTSTRAP_STATE_REPAIR_NEEDED,
    BOOTSTRAP_VERSION,
    CONFIG_VERSION,
    MachineConfig,
    RUNTIME_MODE_EXTERNAL_POSTGRES,
    RUNTIME_MODE_MANAGED_LOCAL,
    backup_corrupt_machine_config,
    save_machine_config,
    save_recovery_stub,
    try_load_machine_config,
    update_bootstrap_state,
)
from app.infrastructure.local_state.repo_registration_store import (
    IDENTITY_STRENGTH_WEAK_LOCAL,
    RepoRegistration,
    load_repo_registration_for_target,
    register_repo_for_target,
)
from app.infrastructure.db.admin.storage_setup import resolve_storage_selection
from app.infrastructure.host_apps.assets import install_host_assets

__all__ = [
    "INIT_OUTCOME_BLOCKED_CONFIG_CORRUPT",
    "INIT_OUTCOME_BLOCKED_CONFLICT",
    "INIT_OUTCOME_BLOCKED_DEPENDENCY",
    "INIT_OUTCOME_BLOCKED_LOCK",
    "INIT_OUTCOME_INITIALIZED",
    "INIT_OUTCOME_NOOP",
    "INIT_OUTCOME_REPAIRED",
    "InitResult",
    "init_success_presenter_context",
    "run_init",
]


def init_success_presenter_context() -> dict[str, object]:
    """Return concrete values needed by the human init presenter."""

    return {
        "runtime_mode_managed_local": RUNTIME_MODE_MANAGED_LOCAL,
        "identity_strength_weak_local": IDENTITY_STRENGTH_WEAK_LOCAL,
        "fingerprint_summary": fingerprint_summary,
    }


def run_init(
    *,
    repo_root: Path,
    repo_id_override: str | None,
    register_repo_now: bool,
    skip_model_download: bool,
    skip_host_assets: bool,
    storage: str | None = None,
    admin_dsn: str | None = None,
    render_success_lines: Callable[..., list[str]] | None = None,
) -> InitResult:
    """Wire concrete init dependencies into the core runtime initializer."""

    return run_initialize_runtime(
        repo_root=repo_root,
        repo_id_override=repo_id_override,
        register_repo_now=register_repo_now,
        skip_model_download=skip_model_download,
        skip_host_assets=skip_host_assets,
        storage=storage,
        admin_dsn=admin_dsn,
        ports=InitializeRuntimePorts(
            get_shellbrain_home=get_shellbrain_home,
            acquire_init_lock=acquire_init_lock,
            ensure_dependencies=_ensure_dependencies,
            try_load_machine_config=try_load_machine_config,
            backup_corrupt_machine_config=backup_corrupt_machine_config,
            recover_machine_config=_recover_machine_config,
            save_recovery_stub=save_recovery_stub,
            update_bootstrap_state=update_bootstrap_state,
            save_machine_config=save_machine_config,
            load_repo_registration_for_target=load_repo_registration_for_target,
            resolve_storage_selection=resolve_storage_selection,
            ensure_managed_dependencies=_ensure_managed_dependencies,
            build_fresh_machine_config=_build_fresh_machine_config,
            build_external_machine_config=_build_external_machine_config,
            migrate_machine_config=_migrate_machine_config,
            ensure_managed_container=_ensure_managed_container,
            backup_before_repair=_backup_before_repair,
            wait_for_postgres=wait_for_postgres,
            reconcile_database=_reconcile_database,
            apply_schema_migrations=_apply_schema_migrations,
            prewarm_embeddings=prewarm_embeddings,
            register_repo=_register_repo,
            install_host_assets=install_host_assets,
            mark_repair_needed=_mark_repair_needed,
            render_success_lines=render_success_lines or _render_success_lines,
            bootstrap_state_ready=BOOTSTRAP_STATE_READY,
            bootstrap_state_repair_needed=BOOTSTRAP_STATE_REPAIR_NEEDED,
            bootstrap_state_provisioning=BOOTSTRAP_STATE_PROVISIONING,
            runtime_mode_managed_local=RUNTIME_MODE_MANAGED_LOCAL,
            runtime_mode_external_postgres=RUNTIME_MODE_EXTERNAL_POSTGRES,
        ),
    )


def _ensure_dependencies() -> None:
    """Verify shared bootstrap dependencies before mutation."""

    if sys.version_info < (3, 11):
        raise InitDependencyError("Python 3.11+ required for `shellbrain init`.")


def _ensure_managed_dependencies() -> None:
    """Verify managed-local runtime prerequisites before mutation."""

    ensure_managed_runtime_available()


def _build_fresh_machine_config() -> MachineConfig:
    """Construct a fresh machine config for managed-local mode."""

    return managed_runtime.build_fresh_machine_config(
        embeddings=_runtime_embeddings_config()
    )


def _build_external_machine_config(*, admin_dsn: str) -> MachineConfig:
    """Construct a fresh external-Postgres machine config."""

    try:
        return external_runtime.build_fresh_machine_config(
            admin_dsn=admin_dsn,
            embeddings=_runtime_embeddings_config(),
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return external_runtime.build_fresh_machine_config(admin_dsn)


def _migrate_machine_config(config: MachineConfig) -> MachineConfig:
    """Upgrade a machine config to the current schema versions."""

    if (
        config.config_version > CONFIG_VERSION
        or config.bootstrap_version > BOOTSTRAP_VERSION
    ):
        raise InitConflictError(
            "Machine config version is newer than this Shellbrain build can manage."
        )
    if config.runtime_mode == RUNTIME_MODE_MANAGED_LOCAL and config.managed is None:
        raise InitConflictError(
            "Managed-local Shellbrain config is missing managed container metadata."
        )
    if (
        config.config_version == CONFIG_VERSION
        and config.bootstrap_version == BOOTSTRAP_VERSION
    ):
        return config
    return MachineConfig(
        config_version=CONFIG_VERSION,
        bootstrap_version=BOOTSTRAP_VERSION,
        instance_id=config.machine_instance_id,
        runtime_mode=config.runtime_mode,
        bootstrap_state=config.bootstrap_state,
        current_step=config.current_step,
        last_error=config.last_error,
        database=config.database,
        managed=config.managed,
        backups=config.backups,
        embeddings=config.embeddings,
    )


def _ensure_managed_container(config: MachineConfig) -> bool:
    """Create or start the managed Postgres container."""

    return managed_runtime.ensure_managed_container(config)


def _backup_before_repair(config: MachineConfig) -> None:
    """Create and verify a logical backup before mutating the configured runtime."""

    if config.runtime_mode == RUNTIME_MODE_MANAGED_LOCAL:
        managed_runtime.backup_before_repair(config)
        return
    if config.runtime_mode == RUNTIME_MODE_EXTERNAL_POSTGRES:
        backup_and_verify_before_destructive_action(
            admin_dsn=config.database.admin_dsn,
            backup_root=Path(config.backups.root),
        )
        return
    raise InitConflictError(
        f"Unsupported runtime mode during backup: {config.runtime_mode}"
    )


def _reconcile_database(config: MachineConfig) -> tuple[bool, MachineConfig]:
    """Create or repair roles, database metadata, extension state, and grants."""

    if config.runtime_mode == RUNTIME_MODE_MANAGED_LOCAL:
        return managed_runtime.reconcile_database(config), config
    if config.runtime_mode == RUNTIME_MODE_EXTERNAL_POSTGRES:
        return external_runtime.reconcile_database(config)
    raise InitConflictError(
        f"Unsupported runtime mode during database reconcile: {config.runtime_mode}"
    )


def _apply_schema_migrations(config: MachineConfig) -> bool:
    """Apply packaged schema migrations to the configured Shellbrain database."""

    from app.startup.migrations import (
        DatabaseMigrationConflictError,
        upgrade_database_for_config,
    )

    try:
        return upgrade_database_for_config(config)
    except DatabaseMigrationConflictError as exc:
        raise InitConflictError(str(exc)) from exc


def _register_repo(
    *,
    repo_root: Path,
    repo_id_override: str | None,
    machine_instance_id: str,
) -> tuple[RepoRegistration, bool]:
    """Register the current repo against the active machine instance."""

    return register_repo_for_target(
        repo_root=repo_root,
        machine_instance_id=machine_instance_id,
        explicit_repo_id=repo_id_override,
    )


def _determine_outcome(
    *,
    mutated_machine: bool,
    mutated_repo: bool,
    existing_registration: RepoRegistration | None,
    repair_performed: bool,
    config_corruption_recovered: bool,
) -> str:
    """Resolve the final init outcome class."""

    if config_corruption_recovered or repair_performed:
        return INIT_OUTCOME_REPAIRED
    if existing_registration is None and mutated_repo:
        return INIT_OUTCOME_INITIALIZED
    if mutated_machine or mutated_repo:
        return INIT_OUTCOME_INITIALIZED
    return INIT_OUTCOME_NOOP


def _render_success_lines(
    *,
    outcome: str,
    config: MachineConfig,
    registration: RepoRegistration | None,
    notes: list[str],
) -> list[str]:
    """Render the init success summary lines without the outcome prefix."""

    del outcome
    if config.runtime_mode == RUNTIME_MODE_MANAGED_LOCAL and config.managed is not None:
        runtime_line = f"Managed instance: {config.managed.container_name} ({config.managed.host}:{config.managed.port})"
    else:
        summary = fingerprint_summary(config.database.admin_dsn)
        runtime_line = f"External database: {summary['host']}:{summary['port']}/{summary['database']}"
    lines = [
        runtime_line,
        f"Embeddings: {config.embeddings.readiness_state}",
        f"Backups: {config.backups.root}",
    ]
    if registration is None:
        lines.append(
            "Repo registration: deferred until first Shellbrain use inside a repo."
        )
        lines.append(
            'Next: from inside a repo, run shellbrain read --json \'{"query":"What prior Shellbrain context matters for this task?","kinds":["problem","solution","failed_tactic","fact","preference","change"]}\''
        )
    else:
        lines.insert(1, f"Repo: {registration.repo_id}")
        if registration.identity_strength == IDENTITY_STRENGTH_WEAK_LOCAL:
            lines.insert(
                2,
                "Repo identity is weak-local and will change if this directory moves. Use --repo-id for a durable override.",
            )
        lines.append(
            'Next: shellbrain read --json \'{"query":"What prior Shellbrain context matters for this task?","kinds":["problem","solution","failed_tactic","fact","preference","change"]}\''
        )
    lines.extend(notes)
    return lines


def _mark_repair_needed(message: str) -> None:
    """Best-effort mark of the machine state after an unexpected init failure."""

    config, error = try_load_machine_config()
    if error is not None or config is None:
        save_recovery_stub(current_step="unexpected_failure", last_error=message)
        return
    save_machine_config(
        update_bootstrap_state(
            config,
            bootstrap_state=BOOTSTRAP_STATE_REPAIR_NEEDED,
            current_step=config.current_step or "unexpected_failure",
            last_error=message,
        )
    )


def _recover_machine_config() -> MachineConfig | None:
    """Attempt to recover one unique managed instance for the current home root."""

    return recover_managed_machine_config(embeddings=_runtime_embeddings_config())


def _runtime_embeddings_config() -> dict[str, object]:
    """Return runtime embedding config for adapter construction."""

    runtime = get_config_provider().get_runtime()
    embeddings = runtime.get("embeddings")
    if not isinstance(embeddings, dict):
        raise RuntimeError("runtime.embeddings must be configured")
    return embeddings
