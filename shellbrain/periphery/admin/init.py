"""Managed Shellbrain bootstrap and repair flow."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from typing import Iterator

import psycopg
from psycopg import sql

from shellbrain.boot.config import get_config_provider
from shellbrain.boot.home import (
    get_machine_backups_dir,
    get_machine_lock_path,
    get_machine_models_dir,
    get_machine_postgres_data_dir,
    get_shellbrain_home,
)
from shellbrain.periphery.admin.backup import create_backup, verify_backup
from shellbrain.periphery.admin.instance_guard import dsn_fingerprint, ensure_instance_metadata
from shellbrain.periphery.admin.machine_state import (
    BOOTSTRAP_STATE_PROVISIONING,
    BOOTSTRAP_STATE_READY,
    BOOTSTRAP_STATE_REPAIR_NEEDED,
    BOOTSTRAP_VERSION,
    CONFIG_VERSION,
    BackupState,
    DatabaseState,
    EmbeddingRuntimeState,
    MachineConfig,
    ManagedInstanceState,
    backup_corrupt_machine_config,
    load_machine_config,
    save_machine_config,
    save_recovery_stub,
    try_load_machine_config,
    update_bootstrap_state,
)
from shellbrain.periphery.admin.privileges import reconcile_app_role_privileges
from shellbrain.periphery.admin.repo_state import (
    IDENTITY_STRENGTH_WEAK_LOCAL,
    RepoRegistration,
    load_repo_registration,
    register_repo,
)
from shellbrain.periphery.identity.claude_hook_install import install_claude_hook
from shellbrain.periphery.identity.claude_runtime import detect_claude_runtime_without_hook


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

_MANAGED_IMAGE = "pgvector/pgvector:pg16"
_MANAGED_DB_NAME = "shellbrain"
_MANAGED_ADMIN_USER = "shellbrain_admin"
_MANAGED_APP_USER = "shellbrain_app"
_MANAGED_HOST = "127.0.0.1"
_MANAGED_LABEL = "io.shellbrain.managed"
_MANAGED_HOME_LABEL = "io.shellbrain.home_sha"
_MANAGED_INSTANCE_LABEL = "io.shellbrain.instance_id"
_MANAGED_PORT_START = 55432
_MANAGED_PORT_END = 55499
_LOCK_TIMEOUT_SECONDS = 30
_STALE_LOCK_MINUTES = 15


class InitDependencyError(RuntimeError):
    """Raised when one bootstrap dependency is missing."""


class InitConflictError(RuntimeError):
    """Raised when managed resources cannot be adopted safely."""


class InitLockError(RuntimeError):
    """Raised when the machine init lock cannot be acquired safely."""


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
    host_mode: str,
    skip_model_download: bool,
) -> InitResult:
    """Bootstrap or repair the managed Shellbrain environment."""

    home_root = get_shellbrain_home()
    home_root.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    mutated_machine = False
    mutated_repo = False
    config_corruption_recovered = False
    repair_performed = False
    existing_registration = load_repo_registration(repo_root)

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
                    save_recovery_stub(
                        current_step="config_recovery",
                        last_error=machine_error,
                    )
                    return InitResult(
                        outcome=INIT_OUTCOME_BLOCKED_CONFIG_CORRUPT,
                        lines=[
                            "Unable to recover a managed Shellbrain instance from the corrupt machine config.",
                            "Rerun after resolving Docker/resource conflicts or remove the corrupt config manually if this is a fresh install.",
                            *notes,
                        ],
                    )
                machine_config = update_bootstrap_state(
                    recovered,
                    bootstrap_state=BOOTSTRAP_STATE_REPAIR_NEEDED,
                    current_step="config_recovery",
                    last_error=machine_error,
                )
                save_machine_config(machine_config)
                config_corruption_recovered = True
                mutated_machine = True

            if machine_config is None:
                machine_config = _build_fresh_machine_config()
                save_machine_config(machine_config)
                mutated_machine = True

            machine_config = _migrate_machine_config(machine_config)
            should_repair = (
                machine_config.bootstrap_state == BOOTSTRAP_STATE_REPAIR_NEEDED or config_corruption_recovered
            )
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
                notes.append("Created a backup before repairing the managed instance.")
                repair_performed = True

            _wait_for_postgres(machine_config.database.admin_dsn)

            machine_config = update_bootstrap_state(
                machine_config,
                bootstrap_state=BOOTSTRAP_STATE_PROVISIONING,
                current_step="database_reconcile",
                last_error=None,
            )
            save_machine_config(machine_config)
            db_changed = _reconcile_database(machine_config)
            mutated_machine = mutated_machine or db_changed

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
            registration, repo_changed = _register_repo(
                repo_root=repo_root,
                repo_id_override=repo_id_override,
                machine_instance_id=machine_config.machine_instance_id,
            )
            mutated_repo = mutated_repo or repo_changed

            claude_note = _handle_claude_integration(
                repo_root=repo_root,
                registration=registration,
                host_mode=host_mode,
            )
            if claude_note:
                notes.append(claude_note)
                registration = register_repo(
                    repo_root=repo_root,
                    machine_instance_id=machine_config.machine_instance_id,
                    explicit_repo_id=registration.repo_id if registration.identity_strength == "explicit" else None,
                    claude_status=_claude_status_for_note(claude_note),
                    claude_settings_path=str(repo_root / ".claude" / "settings.local.json") if "Installed Claude hook" in claude_note else registration.claude_settings_path,
                    claude_note=claude_note,
                )
                mutated_repo = True

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
    """Verify bootstrap dependencies before mutation."""

    if sys.version_info < (3, 11):
        raise InitDependencyError("Shellbrain init requires Python 3.11 or newer.")
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

    runtime = get_config_provider().get_runtime()
    embeddings = runtime.get("embeddings")
    if not isinstance(embeddings, dict):
        raise RuntimeError("runtime.embeddings must be configured")
    home_hash = _home_hash()
    port = _select_managed_port()
    admin_password = secrets.token_hex(16)
    app_password = secrets.token_hex(16)
    admin_dsn = f"postgresql+psycopg://{_MANAGED_ADMIN_USER}:{admin_password}@{_MANAGED_HOST}:{port}/{_MANAGED_DB_NAME}"
    app_dsn = f"postgresql+psycopg://{_MANAGED_APP_USER}:{app_password}@{_MANAGED_HOST}:{port}/{_MANAGED_DB_NAME}"
    instance_id = dsn_fingerprint(admin_dsn)
    return MachineConfig(
        config_version=CONFIG_VERSION,
        bootstrap_version=BOOTSTRAP_VERSION,
        runtime_mode="managed_local",
        bootstrap_state=BOOTSTRAP_STATE_PROVISIONING,
        current_step="bootstrap",
        last_error=None,
        database=DatabaseState(app_dsn=app_dsn, admin_dsn=admin_dsn),
        managed=ManagedInstanceState(
            instance_id=instance_id,
            container_name=f"shellbrain-postgres-{home_hash[:8]}",
            image=_MANAGED_IMAGE,
            host=_MANAGED_HOST,
            port=port,
            db_name=_MANAGED_DB_NAME,
            data_dir=str(get_machine_postgres_data_dir()),
            admin_user=_MANAGED_ADMIN_USER,
            admin_password=admin_password,
            app_user=_MANAGED_APP_USER,
            app_password=app_password,
        ),
        backups=BackupState(root=str(get_machine_backups_dir()), mirror_root=None),
        embeddings=EmbeddingRuntimeState(
            provider=str(embeddings.get("provider") or "sentence_transformers"),
            model=str(embeddings.get("model") or "all-MiniLM-L6-v2"),
            model_revision=None,
            backend_version=None,
            cache_path=str(get_machine_models_dir()),
            readiness_state="pending",
            last_error=None,
        ),
    )


def _migrate_machine_config(config: MachineConfig) -> MachineConfig:
    """Upgrade a machine config to the current schema versions."""

    if config.config_version > CONFIG_VERSION or config.bootstrap_version > BOOTSTRAP_VERSION:
        raise InitConflictError("Machine config version is newer than this Shellbrain build can manage.")
    if config.config_version == CONFIG_VERSION and config.bootstrap_version == BOOTSTRAP_VERSION:
        return config
    return MachineConfig(
        config_version=CONFIG_VERSION,
        bootstrap_version=BOOTSTRAP_VERSION,
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

    info = _inspect_container(config.managed.container_name)
    if info is None:
        _create_managed_container(config)
        _start_container(config.managed.container_name)
        return True
    labels = info.get("Config", {}).get("Labels", {}) or {}
    if labels.get(_MANAGED_LABEL) != "true" or labels.get(_MANAGED_HOME_LABEL) != _home_hash():
        raise InitConflictError(
            f"Container {config.managed.container_name} already exists but is not owned by Shellbrain for this machine state."
        )
    if labels.get(_MANAGED_INSTANCE_LABEL) != config.machine_instance_id:
        raise InitConflictError(
            f"Managed container {config.managed.container_name} does not match the configured Shellbrain instance id."
        )
    state = info.get("State", {}) or {}
    if not state.get("Running"):
        _start_container(config.managed.container_name)
        return True
    return False


def _create_managed_container(config: MachineConfig) -> None:
    """Create the managed Postgres container with Shellbrain-owned labels."""

    data_dir = Path(config.managed.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "docker",
        "create",
        "--name",
        config.managed.container_name,
        "--label",
        f"{_MANAGED_LABEL}=true",
        "--label",
        f"{_MANAGED_HOME_LABEL}={_home_hash()}",
        "--label",
        f"{_MANAGED_INSTANCE_LABEL}={config.machine_instance_id}",
        "--health-cmd",
        f"pg_isready -U {config.managed.admin_user} -d {config.managed.db_name}",
        "--health-interval",
        "10s",
        "--health-timeout",
        "5s",
        "--health-retries",
        "10",
        "-e",
        f"POSTGRES_DB={config.managed.db_name}",
        "-e",
        f"POSTGRES_USER={config.managed.admin_user}",
        "-e",
        f"POSTGRES_PASSWORD={config.managed.admin_password}",
        "-e",
        f"SHELLBRAIN_APP_USER={config.managed.app_user}",
        "-e",
        f"SHELLBRAIN_APP_PASSWORD={config.managed.app_password}",
        "-p",
        f"{config.managed.port}:5432",
        "-v",
        f"{config.managed.data_dir}:/var/lib/postgresql/data",
        config.managed.image,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise InitConflictError(completed.stderr.strip() or f"Failed to create container {config.managed.container_name}.")


def _start_container(container_name: str) -> None:
    """Start one existing Docker container."""

    completed = subprocess.run(
        ["docker", "start", container_name],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise InitConflictError(completed.stderr.strip() or f"Failed to start container {container_name}.")


def _inspect_container(container_name: str) -> dict[str, object] | None:
    """Return one docker inspect payload when the container exists."""

    completed = subprocess.run(
        ["docker", "inspect", container_name],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    payload = json.loads(completed.stdout)
    if not payload:
        return None
    if not isinstance(payload[0], dict):
        return None
    return payload[0]


def _wait_for_postgres(admin_dsn: str) -> None:
    """Wait for managed Postgres to accept connections."""

    deadline = time.time() + 45
    raw_dsn = admin_dsn.replace("+psycopg", "")
    while True:
        try:
            with psycopg.connect(raw_dsn, connect_timeout=2):
                return
        except psycopg.Error:
            if time.time() >= deadline:
                raise InitConflictError("Managed Postgres did not become ready in time.")
            time.sleep(1)


def _backup_before_repair(config: MachineConfig) -> None:
    """Create and verify a logical backup before mutating an existing managed instance."""

    manifest = create_backup(
        admin_dsn=config.database.admin_dsn,
        backup_root=Path(config.backups.root),
        container_name=config.managed.container_name,
        container_db_name=config.managed.db_name,
        container_admin_user=config.managed.admin_user,
        container_admin_password=config.managed.admin_password,
    )
    verify_backup(backup_root=Path(config.backups.root), backup_id=manifest.backup_id)


def _reconcile_database(config: MachineConfig) -> bool:
    """Create or repair managed roles, database, extension, and grants."""

    changed = False
    raw_admin_dsn = config.database.admin_dsn.replace("+psycopg", "")
    postgres_dsn = _replace_database(raw_admin_dsn, "postgres")
    with psycopg.connect(postgres_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (config.managed.db_name,))
            if cur.fetchone() is None:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(config.managed.db_name)))
                changed = True

    with psycopg.connect(raw_admin_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (config.managed.app_user,))
            if cur.fetchone() is None:
                cur.execute(
                    sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %s").format(
                        sql.Identifier(config.managed.app_user)
                    ),
                    (config.managed.app_password,),
                )
                changed = True
            else:
                cur.execute(
                    sql.SQL("ALTER ROLE {} WITH PASSWORD %s").format(sql.Identifier(config.managed.app_user)),
                    (config.managed.app_password,),
                )
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(config.managed.db_name),
                    sql.Identifier(config.managed.app_user),
                )
            )
    reconcile_app_role_privileges(admin_dsn=config.database.admin_dsn, app_dsn=config.database.app_dsn)
    ensure_instance_metadata(
        config.database.admin_dsn,
        instance_mode="live",
        created_by="shellbrain.init",
        notes="Managed local Shellbrain instance",
    )
    return changed


def _prewarm_embeddings(config: MachineConfig, *, skip_model_download: bool) -> tuple[bool, MachineConfig]:
    """Prewarm the configured embedding backend and pin its runtime metadata."""

    backend_version = None
    try:
        backend_version = importlib.metadata.version("sentence-transformers")
    except importlib.metadata.PackageNotFoundError:
        backend_version = None
    if skip_model_download:
        updated = MachineConfig(
            config_version=config.config_version,
            bootstrap_version=config.bootstrap_version,
            runtime_mode=config.runtime_mode,
            bootstrap_state=config.bootstrap_state,
            current_step=config.current_step,
            last_error=config.last_error,
            database=config.database,
            managed=config.managed,
            backups=config.backups,
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
    from shellbrain.periphery.embeddings.local_provider import SentenceTransformersEmbeddingProvider

    provider = SentenceTransformersEmbeddingProvider(
        model=config.embeddings.model,
        cache_folder=config.embeddings.cache_path,
    )
    try:
        provider.embed("shellbrain init warmup")
    except Exception as exc:
        updated = MachineConfig(
            config_version=config.config_version,
            bootstrap_version=config.bootstrap_version,
            runtime_mode=config.runtime_mode,
            bootstrap_state=BOOTSTRAP_STATE_REPAIR_NEEDED,
            current_step="embeddings",
            last_error=str(exc),
            database=config.database,
            managed=config.managed,
            backups=config.backups,
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
    updated = MachineConfig(
        config_version=config.config_version,
        bootstrap_version=config.bootstrap_version,
        runtime_mode=config.runtime_mode,
        bootstrap_state=config.bootstrap_state,
        current_step=config.current_step,
        last_error=config.last_error,
        database=config.database,
        managed=config.managed,
        backups=config.backups,
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

    existing = load_repo_registration(repo_root)
    registration = register_repo(
        repo_root=repo_root,
        machine_instance_id=machine_instance_id,
        explicit_repo_id=repo_id_override,
        claude_status=existing.claude_status if existing is not None else "not_checked",
        claude_settings_path=existing.claude_settings_path if existing is not None else None,
        claude_note=existing.claude_note if existing is not None else None,
    )
    return registration, existing != registration


def _handle_claude_integration(*, repo_root: Path, registration: RepoRegistration, host_mode: str) -> str | None:
    """Install the Claude hook when eligible, otherwise explain why it was skipped."""

    repo_signal = (repo_root / ".claude").exists() or (repo_root / ".claude" / "settings.local.json").exists()
    runtime_signal = detect_claude_runtime_without_hook()
    if host_mode == "none" or host_mode == "auto" and not repo_signal:
        return None
    if host_mode == "auto" and not runtime_signal:
        return "Claude repo detected but no active Claude runtime was found. Rerun from Claude Code or pass --host claude to install the Shellbrain hook."
    if host_mode == "claude" or (repo_signal and runtime_signal):
        settings_path = install_claude_hook(repo_root=repo_root)
        return f"Installed Claude hook at {settings_path}"
    return None


def _claude_status_for_note(note: str) -> str:
    """Return repo-local Claude status for one init note."""

    if note.startswith("Installed Claude hook"):
        return "installed"
    if note.startswith("Claude repo detected"):
        return "eligible_repo_only"
    return "not_applicable"


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
    registration: RepoRegistration,
    notes: list[str],
) -> list[str]:
    """Render the init success summary lines without the outcome prefix."""

    lines = [
        f"Managed instance: {config.managed.container_name} ({config.managed.host}:{config.managed.port})",
        f"Repo: {registration.repo_id}",
        f"Embeddings: {config.embeddings.readiness_state}",
        f"Backups: {config.backups.root}",
        f"Next: shellbrain read --json '{{\"query\":\"What prior Shellbrain context matters for this task?\",\"kinds\":[\"problem\",\"solution\",\"failed_tactic\",\"fact\",\"preference\",\"change\"]}}'",
    ]
    if registration.identity_strength == IDENTITY_STRENGTH_WEAK_LOCAL:
        lines.insert(1, "Repo identity is weak-local and will change if this directory moves. Use --repo-id for a durable override.")
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

    completed = subprocess.run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label={_MANAGED_LABEL}=true",
            "--filter",
            f"label={_MANAGED_HOME_LABEL}={_home_hash()}",
            "--format",
            "{{.Names}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    names = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(names) != 1:
        return None
    info = _inspect_container(names[0])
    if info is None:
        return None
    env_map: dict[str, str] = {}
    for item in info.get("Config", {}).get("Env", []) or []:
        if not isinstance(item, str) or "=" not in item:
            continue
        key, value = item.split("=", 1)
        env_map[key] = value
    network_settings = info.get("NetworkSettings", {}) or {}
    ports = network_settings.get("Ports", {}) or {}
    host_entries = ports.get("5432/tcp") or []
    if not host_entries or not isinstance(host_entries[0], dict):
        return None
    port = int(host_entries[0]["HostPort"])
    admin_password = env_map.get("POSTGRES_PASSWORD")
    app_password = env_map.get("SHELLBRAIN_APP_PASSWORD")
    if not admin_password or not app_password:
        return None
    admin_dsn = f"postgresql+psycopg://{_MANAGED_ADMIN_USER}:{admin_password}@{_MANAGED_HOST}:{port}/{_MANAGED_DB_NAME}"
    app_dsn = f"postgresql+psycopg://{_MANAGED_APP_USER}:{app_password}@{_MANAGED_HOST}:{port}/{_MANAGED_DB_NAME}"
    return MachineConfig(
        config_version=CONFIG_VERSION,
        bootstrap_version=BOOTSTRAP_VERSION,
        runtime_mode="managed_local",
        bootstrap_state=BOOTSTRAP_STATE_REPAIR_NEEDED,
        current_step="config_recovery",
        last_error=None,
        database=DatabaseState(app_dsn=app_dsn, admin_dsn=admin_dsn),
        managed=ManagedInstanceState(
            instance_id=dsn_fingerprint(admin_dsn),
            container_name=names[0],
            image=str(info.get("Config", {}).get("Image") or _MANAGED_IMAGE),
            host=_MANAGED_HOST,
            port=port,
            db_name=env_map.get("POSTGRES_DB", _MANAGED_DB_NAME),
            data_dir=str(get_machine_postgres_data_dir()),
            admin_user=env_map.get("POSTGRES_USER", _MANAGED_ADMIN_USER),
            admin_password=admin_password,
            app_user=env_map.get("SHELLBRAIN_APP_USER", _MANAGED_APP_USER),
            app_password=app_password,
        ),
        backups=BackupState(root=str(get_machine_backups_dir()), mirror_root=None),
        embeddings=EmbeddingRuntimeState(
            provider="sentence_transformers",
            model=str(get_config_provider().get_runtime()["embeddings"]["model"]),
            model_revision=None,
            backend_version=None,
            cache_path=str(get_machine_models_dir()),
            readiness_state="pending",
            last_error=None,
        ),
    )


def _select_managed_port() -> int:
    """Select a free reserved port for the managed Postgres instance."""

    for port in range(_MANAGED_PORT_START, _MANAGED_PORT_END + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((_MANAGED_HOST, port))
            except OSError:
                continue
            return port
    raise InitConflictError("No free reserved port is available for the managed Shellbrain Postgres instance.")


def _replace_database(dsn: str, db_name: str) -> str:
    """Replace the database path component of a DSN."""

    prefix, _, _ = dsn.rpartition("/")
    return f"{prefix}/{db_name}"


def _home_hash() -> str:
    """Return a stable short hash for the active Shellbrain home root."""

    import hashlib

    return hashlib.sha256(str(get_shellbrain_home()).encode("utf-8")).hexdigest()[:16]
