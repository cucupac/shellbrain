"""Core init orchestration for Shellbrain runtime bootstrap and repair."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.entities.admin_errors import (
    InitConflictError,
    InitDependencyError,
    InitLockError,
)


INIT_OUTCOME_INITIALIZED = "initialized"
INIT_OUTCOME_NOOP = "noop"
INIT_OUTCOME_REPAIRED = "repaired"
INIT_OUTCOME_BLOCKED_CONFLICT = "blocked_conflict"
INIT_OUTCOME_BLOCKED_LOCK = "blocked_lock"
INIT_OUTCOME_BLOCKED_DEPENDENCY = "blocked_dependency"
INIT_OUTCOME_BLOCKED_CONFIG_CORRUPT = "blocked_config_corrupt"

INIT_EXIT_CODES = {
    INIT_OUTCOME_INITIALIZED: 0,
    INIT_OUTCOME_NOOP: 0,
    INIT_OUTCOME_REPAIRED: 0,
    INIT_OUTCOME_BLOCKED_CONFLICT: 10,
    INIT_OUTCOME_BLOCKED_LOCK: 11,
    INIT_OUTCOME_BLOCKED_DEPENDENCY: 12,
    INIT_OUTCOME_BLOCKED_CONFIG_CORRUPT: 13,
}


@dataclass(frozen=True)
class InitResult:
    """Structured init outcome and user-facing notes."""

    outcome: str
    lines: list[str]

    @property
    def exit_code(self) -> int:
        """Return the stable exit code for this outcome."""

        return INIT_EXIT_CODES[self.outcome]


@dataclass(frozen=True)
class InitializeRuntimePorts:
    """Concrete effects used by the init use case."""

    get_shellbrain_home: Callable[[], Path]
    acquire_init_lock: Callable[[], Any]
    ensure_dependencies: Callable[[], None]
    try_load_machine_config: Callable[[], tuple[Any | None, str | None]]
    backup_corrupt_machine_config: Callable[[], Path | None]
    recover_machine_config: Callable[[], Any | None]
    save_recovery_stub: Callable[..., None]
    update_bootstrap_state: Callable[..., Any]
    save_machine_config: Callable[[Any], None]
    load_repo_registration_for_target: Callable[[Path], Any | None]
    resolve_storage_selection: Callable[..., Any]
    ensure_managed_dependencies: Callable[[], None]
    build_fresh_machine_config: Callable[[], Any]
    build_external_machine_config: Callable[..., Any]
    migrate_machine_config: Callable[[Any], Any]
    ensure_managed_container: Callable[[Any], bool]
    backup_before_repair: Callable[[Any], None]
    wait_for_postgres: Callable[[str], None]
    reconcile_database: Callable[[Any], tuple[bool, Any]]
    apply_schema_migrations: Callable[[Any], bool]
    prewarm_embeddings: Callable[..., tuple[bool, Any]]
    register_repo: Callable[..., tuple[Any, bool]]
    install_host_assets: Callable[..., Any]
    mark_repair_needed: Callable[[str], None]
    render_success_lines: Callable[..., list[str]]
    bootstrap_state_ready: str
    bootstrap_state_repair_needed: str
    bootstrap_state_provisioning: str
    runtime_mode_managed_local: str
    runtime_mode_external_postgres: str


def run_initialize_runtime(
    *,
    repo_root: Path,
    repo_id_override: str | None,
    register_repo_now: bool,
    skip_model_download: bool,
    skip_host_assets: bool,
    ports: InitializeRuntimePorts,
    storage: str | None = None,
    admin_dsn: str | None = None,
) -> InitResult:
    """Bootstrap or repair the machine-local Shellbrain environment."""

    home_root = ports.get_shellbrain_home()
    home_root.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    mutated_machine = False
    mutated_repo = False
    config_corruption_recovered = False
    repair_performed = False
    existing_registration = ports.load_repo_registration_for_target(repo_root)

    try:
        with ports.acquire_init_lock():
            ports.ensure_dependencies()
            machine_config, machine_error = ports.try_load_machine_config()
            if machine_error:
                backup_path = ports.backup_corrupt_machine_config()
                if backup_path is not None:
                    notes.append(f"Preserved corrupt machine config at {backup_path}")
                recovered = ports.recover_machine_config()
                if recovered is None:
                    ports.save_recovery_stub(
                        current_step="config_recovery", last_error=machine_error
                    )
                    lines = [
                        "Unable to recover Shellbrain runtime state from the corrupt machine config."
                    ]
                    if backup_path is not None:
                        lines.append(
                            f"Preserved corrupt machine config at {backup_path}"
                        )
                    lines.append(
                        "Rerun `shellbrain init` after repairing or replacing the runtime configuration."
                    )
                    return InitResult(
                        outcome=INIT_OUTCOME_BLOCKED_CONFIG_CORRUPT, lines=lines
                    )
                machine_config = ports.update_bootstrap_state(
                    recovered,
                    bootstrap_state=ports.bootstrap_state_repair_needed,
                    current_step="config_recovery",
                    last_error=machine_error,
                )
                ports.save_machine_config(machine_config)
                config_corruption_recovered = True
                mutated_machine = True

            if (
                machine_config is not None
                and machine_config.bootstrap_state == ports.bootstrap_state_ready
                and not config_corruption_recovered
            ):
                if not skip_host_assets:
                    notes.extend(
                        ports.install_host_assets(host_mode="auto", force=False).lines
                    )
                return InitResult(outcome=INIT_OUTCOME_NOOP, lines=notes)

            selection = ports.resolve_storage_selection(
                existing_config=machine_config,
                storage_flag=storage,
                admin_dsn_flag=admin_dsn,
            )

            if machine_config is None:
                if selection.runtime_mode == ports.runtime_mode_managed_local:
                    ports.ensure_managed_dependencies()
                    machine_config = ports.build_fresh_machine_config()
                else:
                    if selection.admin_dsn is None:
                        raise InitDependencyError(
                            "Shellbrain init needs --admin-dsn when bootstrapping external PostgreSQL non-interactively."
                        )
                    machine_config = ports.build_external_machine_config(
                        admin_dsn=selection.admin_dsn
                    )
                ports.save_machine_config(machine_config)
                mutated_machine = True

            machine_config = ports.migrate_machine_config(machine_config)
            should_repair = (
                machine_config.bootstrap_state == ports.bootstrap_state_repair_needed
                or config_corruption_recovered
            )

            if machine_config.runtime_mode == ports.runtime_mode_managed_local:
                ports.ensure_managed_dependencies()
                machine_config = ports.update_bootstrap_state(
                    machine_config,
                    bootstrap_state=ports.bootstrap_state_provisioning,
                    current_step="managed_instance",
                    last_error=None,
                )
                ports.save_machine_config(machine_config)
                container_changed = ports.ensure_managed_container(machine_config)
                mutated_machine = mutated_machine or container_changed

            if should_repair:
                ports.backup_before_repair(machine_config)
                notes.append(
                    "Created a backup before repairing the configured Shellbrain runtime."
                )
                repair_performed = True

            ports.wait_for_postgres(machine_config.database.admin_dsn)

            machine_config = ports.update_bootstrap_state(
                machine_config,
                bootstrap_state=ports.bootstrap_state_provisioning,
                current_step="database_reconcile",
                last_error=None,
            )
            ports.save_machine_config(machine_config)
            db_changed, machine_config = ports.reconcile_database(machine_config)
            mutated_machine = mutated_machine or db_changed
            ports.save_machine_config(machine_config)

            machine_config = ports.update_bootstrap_state(
                machine_config,
                bootstrap_state=ports.bootstrap_state_provisioning,
                current_step="schema_migrate",
                last_error=None,
            )
            ports.save_machine_config(machine_config)
            schema_changed = ports.apply_schema_migrations(machine_config)
            mutated_machine = mutated_machine or schema_changed

            machine_config = ports.update_bootstrap_state(
                machine_config,
                bootstrap_state=ports.bootstrap_state_provisioning,
                current_step="embeddings",
                last_error=None,
            )
            ports.save_machine_config(machine_config)
            embedding_changed, machine_config = ports.prewarm_embeddings(
                machine_config,
                skip_model_download=skip_model_download,
            )
            ports.save_machine_config(machine_config)
            mutated_machine = mutated_machine or embedding_changed

            machine_config = ports.update_bootstrap_state(
                machine_config,
                bootstrap_state=ports.bootstrap_state_provisioning,
                current_step="repo_registration",
                last_error=None,
            )
            ports.save_machine_config(machine_config)
            registration = None
            if register_repo_now:
                registration, repo_changed = ports.register_repo(
                    repo_root=repo_root,
                    repo_id_override=repo_id_override,
                    machine_instance_id=machine_config.machine_instance_id,
                )
                mutated_repo = mutated_repo or repo_changed

            if skip_host_assets:
                notes.extend(
                    [
                        "Codex startup guidance: skipped (--no-host-assets)",
                        "Codex skill: skipped (--no-host-assets)",
                        "Claude startup guidance: skipped (--no-host-assets)",
                        "Claude skill: skipped (--no-host-assets)",
                        "Cursor skill: skipped (--no-host-assets)",
                        "Claude global hook: skipped (--no-host-assets)",
                    ]
                )
            else:
                notes.extend(
                    ports.install_host_assets(host_mode="auto", force=False).lines
                )

            machine_config = ports.update_bootstrap_state(
                machine_config,
                bootstrap_state=ports.bootstrap_state_ready,
                current_step="verification",
                last_error=None,
            )
            ports.save_machine_config(machine_config)

            outcome = _determine_outcome(
                mutated_machine=mutated_machine,
                mutated_repo=mutated_repo,
                existing_registration=existing_registration,
                repair_performed=repair_performed,
                config_corruption_recovered=config_corruption_recovered,
            )
            lines = ports.render_success_lines(
                outcome=outcome,
                config=machine_config,
                registration=registration,
                notes=notes,
            )
            return InitResult(outcome=outcome, lines=lines)
    except InitDependencyError as exc:
        return InitResult(outcome=INIT_OUTCOME_BLOCKED_DEPENDENCY, lines=[str(exc)])
    except InitConflictError as exc:
        ports.mark_repair_needed(str(exc))
        return InitResult(outcome=INIT_OUTCOME_BLOCKED_CONFLICT, lines=[str(exc)])
    except InitLockError as exc:
        return InitResult(outcome=INIT_OUTCOME_BLOCKED_LOCK, lines=[str(exc)])
    except Exception as exc:  # pragma: no cover - fail closed in init path
        ports.mark_repair_needed(str(exc))
        raise


def _determine_outcome(
    *,
    mutated_machine: bool,
    mutated_repo: bool,
    existing_registration: Any | None,
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
