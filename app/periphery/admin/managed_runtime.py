"""Managed Docker-backed PostgreSQL runtime helpers for Shellbrain init."""

from __future__ import annotations

import json
from pathlib import Path
import secrets
import socket
import subprocess

import psycopg
from psycopg import sql

from app.boot.config import get_config_provider
from app.boot.home import get_machine_backups_dir, get_machine_models_dir, get_machine_postgres_data_dir, get_shellbrain_home
from app.periphery.admin.destructive_guard import backup_and_verify_before_destructive_action
from app.periphery.admin.init_errors import InitConflictError
from app.periphery.admin.instance_guard import dsn_fingerprint, ensure_instance_metadata
from app.periphery.admin.machine_state import (
    BOOTSTRAP_STATE_REPAIR_NEEDED,
    BOOTSTRAP_STATE_PROVISIONING,
    BOOTSTRAP_VERSION,
    CONFIG_VERSION,
    BackupState,
    DatabaseState,
    EmbeddingRuntimeState,
    MachineConfig,
    ManagedInstanceState,
    RUNTIME_MODE_MANAGED_LOCAL,
)
from app.periphery.admin.privileges import reconcile_app_role_privileges


MANAGED_IMAGE = "pgvector/pgvector:pg16"
MANAGED_DB_NAME = "shellbrain"
MANAGED_ADMIN_USER = "shellbrain_admin"
MANAGED_APP_USER = "shellbrain_app"
MANAGED_HOST = "127.0.0.1"
MANAGED_LABEL = "io.shellbrain.managed"
MANAGED_HOME_LABEL = "io.shellbrain.home_sha"
MANAGED_INSTANCE_LABEL = "io.shellbrain.instance_id"
MANAGED_PORT_START = 55432
MANAGED_PORT_END = 55499


def build_fresh_machine_config() -> MachineConfig:
    """Construct a fresh machine config for managed-local mode."""

    runtime = get_config_provider().get_runtime()
    embeddings = runtime.get("embeddings")
    if not isinstance(embeddings, dict):
        raise RuntimeError("runtime.embeddings must be configured")
    home_hash = _home_hash()
    port = _select_managed_port()
    admin_password = secrets.token_hex(16)
    app_password = secrets.token_hex(16)
    admin_dsn = f"postgresql+psycopg://{MANAGED_ADMIN_USER}:{admin_password}@{MANAGED_HOST}:{port}/{MANAGED_DB_NAME}"
    app_dsn = f"postgresql+psycopg://{MANAGED_APP_USER}:{app_password}@{MANAGED_HOST}:{port}/{MANAGED_DB_NAME}"
    instance_id = dsn_fingerprint(admin_dsn)
    return MachineConfig(
        config_version=CONFIG_VERSION,
        bootstrap_version=BOOTSTRAP_VERSION,
        instance_id=instance_id,
        runtime_mode=RUNTIME_MODE_MANAGED_LOCAL,
        bootstrap_state=BOOTSTRAP_STATE_PROVISIONING,
        current_step="bootstrap",
        last_error=None,
        database=DatabaseState(app_dsn=app_dsn, admin_dsn=admin_dsn),
        managed=ManagedInstanceState(
            instance_id=instance_id,
            container_name=f"shellbrain-postgres-{home_hash[:8]}",
            image=MANAGED_IMAGE,
            host=MANAGED_HOST,
            port=port,
            db_name=MANAGED_DB_NAME,
            data_dir=str(get_machine_postgres_data_dir()),
            admin_user=MANAGED_ADMIN_USER,
            admin_password=admin_password,
            app_user=MANAGED_APP_USER,
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


def ensure_managed_container(config: MachineConfig) -> bool:
    """Create or start the managed Postgres container."""

    if config.managed is None:
        raise InitConflictError("Managed-local Shellbrain config is missing managed container metadata.")
    info = inspect_container(config.managed.container_name)
    if info is None:
        _create_managed_container(config)
        _start_container(config.managed.container_name)
        return True
    labels = info.get("Config", {}).get("Labels", {}) or {}
    if labels.get(MANAGED_LABEL) != "true" or labels.get(MANAGED_HOME_LABEL) != _home_hash():
        raise InitConflictError(
            f"Container {config.managed.container_name} already exists but is not owned by Shellbrain for this machine state."
        )
    if labels.get(MANAGED_INSTANCE_LABEL) != config.machine_instance_id:
        raise InitConflictError(
            f"Managed container {config.managed.container_name} does not match the configured Shellbrain instance id."
        )
    state = info.get("State", {}) or {}
    if not state.get("Running"):
        _start_container(config.managed.container_name)
        return True
    return False


def backup_before_repair(config: MachineConfig) -> None:
    """Create and verify a logical backup before mutating a managed instance."""

    if config.managed is None:
        raise InitConflictError("Managed-local Shellbrain config is missing managed container metadata.")
    backup_and_verify_before_destructive_action(
        admin_dsn=config.database.admin_dsn,
        backup_root=Path(config.backups.root),
        container_name=config.managed.container_name,
        container_db_name=config.managed.db_name,
        container_admin_user=config.managed.admin_user,
        container_admin_password=config.managed.admin_password,
    )


def reconcile_database(config: MachineConfig) -> bool:
    """Create or repair managed roles, database, extension, and grants."""

    if config.managed is None:
        raise InitConflictError("Managed-local Shellbrain config is missing managed container metadata.")
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
                    sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                        sql.Identifier(config.managed.app_user),
                        sql.Literal(config.managed.app_password),
                    ),
                )
                changed = True
            else:
                cur.execute(
                    sql.SQL("ALTER ROLE {} WITH PASSWORD {}").format(
                        sql.Identifier(config.managed.app_user),
                        sql.Literal(config.managed.app_password),
                    ),
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
        created_by="app.init",
        notes="Managed local Shellbrain instance",
    )
    return changed


def recover_machine_config_from_docker() -> MachineConfig | None:
    """Attempt to recover one unique managed instance for the current home root."""

    completed = subprocess.run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label={MANAGED_LABEL}=true",
            "--filter",
            f"label={MANAGED_HOME_LABEL}={_home_hash()}",
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
    info = inspect_container(names[0])
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
    admin_dsn = f"postgresql+psycopg://{MANAGED_ADMIN_USER}:{admin_password}@{MANAGED_HOST}:{port}/{MANAGED_DB_NAME}"
    app_dsn = f"postgresql+psycopg://{MANAGED_APP_USER}:{app_password}@{MANAGED_HOST}:{port}/{MANAGED_DB_NAME}"
    runtime = get_config_provider().get_runtime()
    embeddings = runtime.get("embeddings")
    if not isinstance(embeddings, dict):
        return None
    instance_id = dsn_fingerprint(admin_dsn)
    return MachineConfig(
        config_version=CONFIG_VERSION,
        bootstrap_version=BOOTSTRAP_VERSION,
        instance_id=instance_id,
        runtime_mode=RUNTIME_MODE_MANAGED_LOCAL,
        bootstrap_state=BOOTSTRAP_STATE_REPAIR_NEEDED,
        current_step="config_recovery",
        last_error=None,
        database=DatabaseState(app_dsn=app_dsn, admin_dsn=admin_dsn),
        managed=ManagedInstanceState(
            instance_id=instance_id,
            container_name=names[0],
            image=str(info.get("Config", {}).get("Image") or MANAGED_IMAGE),
            host=MANAGED_HOST,
            port=port,
            db_name=env_map.get("POSTGRES_DB", MANAGED_DB_NAME),
            data_dir=str(get_machine_postgres_data_dir()),
            admin_user=env_map.get("POSTGRES_USER", MANAGED_ADMIN_USER),
            admin_password=admin_password,
            app_user=env_map.get("SHELLBRAIN_APP_USER", MANAGED_APP_USER),
            app_password=app_password,
        ),
        backups=BackupState(root=str(get_machine_backups_dir()), mirror_root=None),
        embeddings=EmbeddingRuntimeState(
            provider="sentence_transformers",
            model=str(embeddings.get("model") or "all-MiniLM-L6-v2"),
            model_revision=None,
            backend_version=None,
            cache_path=str(get_machine_models_dir()),
            readiness_state="pending",
            last_error=None,
        ),
    )


def inspect_container(container_name: str) -> dict[str, object] | None:
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


def _create_managed_container(config: MachineConfig) -> None:
    """Create the managed Postgres container with Shellbrain-owned labels."""

    assert config.managed is not None
    data_dir = Path(config.managed.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "docker",
        "create",
        "--name",
        config.managed.container_name,
        "--label",
        f"{MANAGED_LABEL}=true",
        "--label",
        f"{MANAGED_HOME_LABEL}={_home_hash()}",
        "--label",
        f"{MANAGED_INSTANCE_LABEL}={config.machine_instance_id}",
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


def _select_managed_port() -> int:
    """Select a free reserved port for the managed Postgres instance."""

    claimed_ports = _managed_claimed_host_ports()
    for port in range(MANAGED_PORT_START, MANAGED_PORT_END + 1):
        if port in claimed_ports:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((MANAGED_HOST, port))
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


def _managed_claimed_host_ports() -> set[int]:
    """Return reserved host ports already claimed by managed Shellbrain containers."""

    completed = subprocess.run(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label={MANAGED_LABEL}=true",
            "--format",
            "{{.Names}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return set()
    ports: set[int] = set()
    for name in (line.strip() for line in completed.stdout.splitlines()):
        if not name:
            continue
        info = inspect_container(name)
        if info is None:
            continue
        ports.update(_container_host_ports(info))
    return ports


def _container_host_ports(info: dict[str, object]) -> set[int]:
    """Extract declared host ports from one Docker inspect payload."""

    ports: set[int] = set()
    host_config = info.get("HostConfig", {}) or {}
    port_bindings = host_config.get("PortBindings", {}) or {}
    for bindings in port_bindings.values():
        if not isinstance(bindings, list):
            continue
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            host_port = binding.get("HostPort")
            if isinstance(host_port, str) and host_port.isdigit():
                ports.add(int(host_port))

    network_settings = info.get("NetworkSettings", {}) or {}
    active_ports = network_settings.get("Ports", {}) or {}
    for bindings in active_ports.values():
        if not isinstance(bindings, list):
            continue
        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            host_port = binding.get("HostPort")
            if isinstance(host_port, str) and host_port.isdigit():
                ports.add(int(host_port))
    return ports
