"""Shellbrain machine bootstrap and repair flow."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from typing import Iterator

import psycopg

from app.boot.home import get_machine_lock_path, get_shellbrain_home
from app.periphery.admin import external_runtime, managed_runtime
from app.periphery.admin.destructive_guard import backup_and_verify_before_destructive_action
from app.periphery.admin.init_errors import InitConflictError, InitDependencyError, InitLockError
from app.periphery.admin.instance_guard import fingerprint_summary
from app.periphery.admin.machine_state import (
    BOOTSTRAP_STATE_PROVISIONING,
    BOOTSTRAP_STATE_READY,
    BOOTSTRAP_STATE_REPAIR_NEEDED,
    BOOTSTRAP_VERSION,
    CONFIG_VERSION,
    EmbeddingRuntimeState,
    MachineConfig,
    RUNTIME_MODE_EXTERNAL_POSTGRES,
    RUNTIME_MODE_MANAGED_LOCAL,
    backup_corrupt_machine_config,
    save_machine_config,
    save_recovery_stub,
    try_load_machine_config,
    update_bootstrap_state,
)
from app.periphery.admin.repo_state import (
    IDENTITY_STRENGTH_WEAK_LOCAL,
    RepoRegistration,
    load_repo_registration_for_target,
    register_repo_for_target,
)
from app.periphery.admin.storage_setup import resolve_storage_selection
from app.periphery.onboarding.host_assets import install_host_assets


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

_LOCK_TIMEOUT_SECONDS = 30
_STALE_LOCK_MINUTES = 15


@dataclass(frozen=True)
class InitResult:
    """Structured init outcome and user-facing notes."""

    outcome: str
    lines: list[str]

    @property
    def exit_code(self) -> int:
        """Return the stable exit code for this outcome."""

        return INIT_EXIT_CODES[self.outcome]


def run_init(
    *,
    repo_root: Path,
    repo_id_override: str | None,
    register_repo_now: bool,
    skip_model_download: bool,
    skip_host_assets: bool,
    storage: str | None = None,
    admin_dsn: str | None = None,
) -> InitResult:
    """Bootstrap or repair the machine-local Shellbrain environment."""

    home_root = get_shellbrain_home()
    home_root.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    mutated_machine = False
    mutated_repo = False
    config_corruption_recovered = False
    repair_performed = False
    existing_registration = load_repo_registration_for_target(repo_root)

    try:
        with _acquire_init_lock():
            _ensure_dependencies()
            machine_config, machine_error = try_load_machine_config()
            if machine_error:
                backup_path = backup_corrupt_machine_config()
                if backup_path is not None:
                    notes.append(f"Preserved corrupt machine config at {backup_path}")
                recovered = _recover_machine_config_from_docker()
                if recovered is None:
                    save_recovery_stub(current_step="config_recovery", last_error=machine_error)
                    lines = ["Unable to recover Shellbrain runtime state from the corrupt machine config."]
                    if backup_path is not None:
                        lines.append(f"Preserved corrupt machine config at {backup_path}")
                    lines.append("Rerun `shellbrain init` after repairing or replacing the runtime configuration.")
                    return InitResult(outcome=INIT_OUTCOME_BLOCKED_CONFIG_CORRUPT, lines=lines)
                machine_config = update_bootstrap_state(
                    recovered,
                    bootstrap_state=BOOTSTRAP_STATE_REPAIR_NEEDED,
                    current_step="config_recovery",
                    last_error=machine_error,
                )
                save_machine_config(machine_config)
                config_corruption_recovered = True
                mutated_machine = True

            selection = resolve_storage_selection(
                existing_config=machine_config,
                storage_flag=storage,
                admin_dsn_flag=admin_dsn,
            )

            if machine_config is None:
                if selection.runtime_mode == RUNTIME_MODE_MANAGED_LOCAL:
                    _ensure_managed_dependencies()
                    machine_config = _build_fresh_machine_config()
                else:
                    if selection.admin_dsn is None:
                        raise InitDependencyError(
                            "Shellbrain init needs --admin-dsn when bootstrapping external PostgreSQL non-interactively."
                        )
                    machine_config = external_runtime.build_fresh_machine_config(admin_dsn=selection.admin_dsn)
                save_machine_config(machine_config)
                mutated_machine = True

            machine_config = _migrate_machine_config(machine_config)
            should_repair = (
                machine_config.bootstrap_state == BOOTSTRAP_STATE_REPAIR_NEEDED or config_corruption_recovered
            )

            if machine_config.runtime_mode == RUNTIME_MODE_MANAGED_LOCAL:
                _ensure_managed_dependencies()
                machine_config = update_bootstrap_state(
                    machine_config,
                    bootstrap_state=BOOTSTRAP_STATE_PROVISIONING,
                    current_step="managed_instance",
                    last_error=None,
                )
                save_machine_config(machine_config)
                container_changed = _ensure_managed_container(machine_config)
                mutated_machine = mutated_machine or container_changed

            if should_repair:
                _backup_before_repair(machine_config)
                notes.append("Created a backup before repairing the configured Shellbrain runtime.")
                repair_performed = True

            _wait_for_postgres(machine_config.database.admin_dsn)

            machine_config = update_bootstrap_state(
                machine_config,
                bootstrap_state=BOOTSTRAP_STATE_PROVISIONING,
                current_step="database_reconcile",
                last_error=None,
            )
            save_machine_config(machine_config)
            db_changed, machine_config = _reconcile_database(machine_config)
            mutated_machine = mutated_machine or db_changed
            save_machine_config(machine_config)

            machine_config = update_bootstrap_state(
                machine_config,
                bootstrap_state=BOOTSTRAP_STATE_PROVISIONING,
                current_step="schema_migrate",
                last_error=None,
            )
            save_machine_config(machine_config)
            schema_changed = _apply_schema_migrations(machine_config)
            mutated_machine = mutated_machine or schema_changed

            machine_config = update_bootstrap_state(
                machine_config,
                bootstrap_state=BOOTSTRAP_STATE_PROVISIONING,
                current_step="embeddings",
                last_error=None,
            )
            save_machine_config(machine_config)
            embedding_changed, machine_config = _prewarm_embeddings(
                machine_config,
                skip_model_download=skip_model_download,
            )
            save_machine_config(machine_config)
            mutated_machine = mutated_machine or embedding_changed

            machine_config = update_bootstrap_state(
                machine_config,
                bootstrap_state=BOOTSTRAP_STATE_PROVISIONING,
                current_step="repo_registration",
                last_error=None,
            )
            save_machine_config(machine_config)
            registration = None
            if register_repo_now:
                registration, repo_changed = _register_repo(
                    repo_root=repo_root,
                    repo_id_override=repo_id_override,
                    machine_instance_id=machine_config.machine_instance_id,
                )
                mutated_repo = mutated_repo or repo_changed

            if skip_host_assets:
                notes.extend(
                    [
                        "Codex skill: skipped (--no-host-assets)",
                        "Claude skill: skipped (--no-host-assets)",
                        "Cursor skill: skipped (--no-host-assets)",
                        "Claude global hook: skipped (--no-host-assets)",
                    ]
                )
            else:
                notes.extend(install_host_assets(host_mode="auto", force=False).lines)

            machine_config = update_bootstrap_state(
                machine_config,
                bootstrap_state=BOOTSTRAP_STATE_READY,
                current_step="verification",
                last_error=None,
            )
            save_machine_config(machine_config)

            outcome = _determine_outcome(
                mutated_machine=mutated_machine,
                mutated_repo=mutated_repo,
                existing_registration=existing_registration,
                repair_performed=repair_performed,
                config_corruption_recovered=config_corruption_recovered,
            )
            lines = _render_success_lines(
                outcome=outcome,
                config=machine_config,
                registration=registration,
                notes=notes,
            )
            return InitResult(outcome=outcome, lines=lines)
    except InitDependencyError as exc:
        return InitResult(outcome=INIT_OUTCOME_BLOCKED_DEPENDENCY, lines=[str(exc)])
    except InitConflictError as exc:
        _mark_repair_needed(str(exc))
        return InitResult(outcome=INIT_OUTCOME_BLOCKED_CONFLICT, lines=[str(exc)])
    except InitLockError as exc:
        return InitResult(outcome=INIT_OUTCOME_BLOCKED_LOCK, lines=[str(exc)])
    except Exception as exc:  # pragma: no cover - fail closed in init path
        _mark_repair_needed(str(exc))
        raise


@contextmanager
def _acquire_init_lock() -> Iterator[None]:
    """Acquire a machine-scoped init lock with stale lock recovery."""

    lock_path = get_machine_lock_path()
    deadline = time.time() + _LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            payload = {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "command": " ".join(sys.argv),
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
            try:
                yield
            finally:
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
            return
        except FileExistsError:
            if _clear_stale_lock(lock_path):
                continue
            if time.time() >= deadline:
                holder = _read_lock_holder(lock_path)
                raise InitLockError(
                    f"Shellbrain init is already running for this machine state. Lock holder: {holder or 'unknown'}"
                )
            time.sleep(1)


def _clear_stale_lock(lock_path: Path) -> bool:
    """Remove one stale init lock when the owning process is gone."""

    holder = _read_lock_payload(lock_path)
    if holder is None:
        return False
    started_at = holder.get("started_at")
    pid = holder.get("pid")
    if not isinstance(started_at, str) or not isinstance(pid, int):
        return False
    age = datetime.now(timezone.utc) - datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    if age < timedelta(minutes=_STALE_LOCK_MINUTES):
        return False
    if _pid_exists(pid):
        return False
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return True
    return True


def _pid_exists(pid: int) -> bool:
    """Return whether one process id still exists."""

    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_lock_payload(lock_path: Path) -> dict[str, object] | None:
    """Return parsed lock metadata when available."""

    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _read_lock_holder(lock_path: Path) -> str | None:
    """Return a short human-readable lock holder description."""

    payload = _read_lock_payload(lock_path)
    if payload is None:
        return None
    pid = payload.get("pid")
    hostname = payload.get("hostname")
    command = payload.get("command")
    return f"pid={pid} host={hostname} command={command}"


def _ensure_dependencies() -> None:
    """Verify shared bootstrap dependencies before mutation."""

    if sys.version_info < (3, 11):
        raise InitDependencyError("Python 3.11+ required for `shellbrain init`.")


def _ensure_managed_dependencies() -> None:
    """Verify managed-local Docker prerequisites before mutation."""

    if shutil.which("docker") is None:
        raise InitDependencyError("Shellbrain init requires Docker to be installed.")
    completed = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise InitDependencyError("Shellbrain init requires the Docker daemon to be running and reachable.")


def _build_fresh_machine_config() -> MachineConfig:
    """Construct a fresh machine config for managed-local mode."""

    return managed_runtime.build_fresh_machine_config()


def _migrate_machine_config(config: MachineConfig) -> MachineConfig:
    """Upgrade a machine config to the current schema versions."""

    if config.config_version > CONFIG_VERSION or config.bootstrap_version > BOOTSTRAP_VERSION:
        raise InitConflictError("Machine config version is newer than this Shellbrain build can manage.")
    if config.runtime_mode == RUNTIME_MODE_MANAGED_LOCAL and config.managed is None:
        raise InitConflictError("Managed-local Shellbrain config is missing managed container metadata.")
    if config.config_version == CONFIG_VERSION and config.bootstrap_version == BOOTSTRAP_VERSION:
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


def _wait_for_postgres(admin_dsn: str) -> None:
    """Wait for the configured PostgreSQL runtime to accept connections."""

    deadline = time.time() + 45
    raw_dsn = admin_dsn.replace("+psycopg", "")
    while True:
        try:
            with psycopg.connect(raw_dsn, connect_timeout=2):
                return
        except psycopg.Error:
            if time.time() >= deadline:
                raise InitConflictError("Shellbrain PostgreSQL runtime did not become ready in time.")
            time.sleep(1)


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
    raise InitConflictError(f"Unsupported runtime mode during backup: {config.runtime_mode}")


def _reconcile_database(config: MachineConfig) -> tuple[bool, MachineConfig]:
    """Create or repair roles, database metadata, extension state, and grants."""

    if config.runtime_mode == RUNTIME_MODE_MANAGED_LOCAL:
        return managed_runtime.reconcile_database(config), config
    if config.runtime_mode == RUNTIME_MODE_EXTERNAL_POSTGRES:
        return external_runtime.reconcile_database(config)
    raise InitConflictError(f"Unsupported runtime mode during database reconcile: {config.runtime_mode}")


def _apply_schema_migrations(config: MachineConfig) -> bool:
    """Apply packaged schema migrations to the configured Shellbrain database."""

    from app.boot.migrations import upgrade_database

    before_revision = _fetch_schema_revision(config.database.admin_dsn)
    upgrade_database()
    after_revision = _fetch_schema_revision(config.database.admin_dsn)
    return before_revision != after_revision


def _fetch_schema_revision(dsn: str) -> str | None:
    """Best-effort read of the current alembic revision."""

    try:
        with psycopg.connect(dsn.replace("+psycopg", "")) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version_num FROM alembic_version")
                row = cur.fetchone()
    except psycopg.Error:
        return None
    if row is None or row[0] is None:
        return None
    return str(row[0])


def _prewarm_embeddings(config: MachineConfig, *, skip_model_download: bool) -> tuple[bool, MachineConfig]:
    """Prewarm the configured embedding backend and pin its runtime metadata."""

    try:
        backend_version = importlib.metadata.version("sentence-transformers")
    except importlib.metadata.PackageNotFoundError:
        backend_version = None
    if skip_model_download:
        updated = replace(
            config,
            embeddings=EmbeddingRuntimeState(
                provider=config.embeddings.provider,
                model=config.embeddings.model,
                model_revision=config.embeddings.model_revision,
                backend_version=backend_version,
                cache_path=config.embeddings.cache_path,
                readiness_state="skipped",
                last_error="Model prewarm was skipped during init.",
            ),
        )
        return True, updated

    os.environ["HF_HOME"] = config.embeddings.cache_path
    Path(config.embeddings.cache_path).mkdir(parents=True, exist_ok=True)
    from app.periphery.embeddings.local_provider import SentenceTransformersEmbeddingProvider

    provider = SentenceTransformersEmbeddingProvider(
        model=config.embeddings.model,
        cache_folder=config.embeddings.cache_path,
    )
    try:
        provider.embed("shellbrain init warmup")
    except Exception as exc:
        updated = replace(
            config,
            bootstrap_state=BOOTSTRAP_STATE_REPAIR_NEEDED,
            current_step="embeddings",
            last_error=str(exc),
            embeddings=EmbeddingRuntimeState(
                provider=config.embeddings.provider,
                model=config.embeddings.model,
                model_revision=config.embeddings.model_revision,
                backend_version=backend_version,
                cache_path=config.embeddings.cache_path,
                readiness_state="failed",
                last_error=str(exc),
            ),
        )
        return True, updated
    updated = replace(
        config,
        embeddings=EmbeddingRuntimeState(
            provider=config.embeddings.provider,
            model=config.embeddings.model,
            model_revision=config.embeddings.model_revision,
            backend_version=backend_version,
            cache_path=config.embeddings.cache_path,
            readiness_state="ready",
            last_error=None,
        ),
    )
    return config.embeddings.readiness_state != "ready" or config.embeddings.backend_version != backend_version, updated


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
    lines = [runtime_line, f"Embeddings: {config.embeddings.readiness_state}", f"Backups: {config.backups.root}"]
    if registration is None:
        lines.append("Repo registration: deferred until first Shellbrain use inside a repo.")
        lines.append(
            "Next: from inside a repo, run shellbrain read --json '{\"query\":\"What prior Shellbrain context matters for this task?\",\"kinds\":[\"problem\",\"solution\",\"failed_tactic\",\"fact\",\"preference\",\"change\"]}'"
        )
    else:
        lines.insert(1, f"Repo: {registration.repo_id}")
        if registration.identity_strength == IDENTITY_STRENGTH_WEAK_LOCAL:
            lines.insert(2, "Repo identity is weak-local and will change if this directory moves. Use --repo-id for a durable override.")
        lines.append(
            "Next: shellbrain read --json '{\"query\":\"What prior Shellbrain context matters for this task?\",\"kinds\":[\"problem\",\"solution\",\"failed_tactic\",\"fact\",\"preference\",\"change\"]}'"
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


def _recover_machine_config_from_docker() -> MachineConfig | None:
    """Attempt to recover one unique managed instance for the current home root."""

    if shutil.which("docker") is None:
        return None
    try:
        return managed_runtime.recover_machine_config_from_docker()
    except FileNotFoundError:
        return None
