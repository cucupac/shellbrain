"""Machine-owned Shellbrain runtime config and bootstrap state."""

from __future__ import annotations

from dataclasses import dataclass


CONFIG_VERSION = 2
BOOTSTRAP_VERSION = 1
RUNTIME_MODE_MANAGED_LOCAL = "managed_local"
RUNTIME_MODE_EXTERNAL_POSTGRES = "external_postgres"
BOOTSTRAP_STATE_PROVISIONING = "provisioning"
BOOTSTRAP_STATE_READY = "ready"
BOOTSTRAP_STATE_REPAIR_NEEDED = "repair_needed"


@dataclass(frozen=True)
class DatabaseState:
    """Resolved application and admin DSNs for the active runtime."""

    app_dsn: str
    admin_dsn: str


@dataclass(frozen=True)
class ManagedInstanceState:
    """Machine-owned managed Postgres runtime metadata."""

    instance_id: str
    container_name: str
    image: str
    host: str
    port: int
    db_name: str
    data_dir: str
    admin_user: str
    admin_password: str
    app_user: str
    app_password: str


@dataclass(frozen=True)
class BackupState:
    """Configured backup directory roots."""

    root: str
    mirror_root: str | None = None


@dataclass(frozen=True)
class EmbeddingRuntimeState:
    """Pinned embedding runtime metadata."""

    provider: str
    model: str
    model_revision: str | None
    backend_version: str | None
    cache_path: str
    readiness_state: str
    last_error: str | None = None


@dataclass(frozen=True)
class MachineConfig:
    """Machine-owned runtime state for Shellbrain bootstrap and repair."""

    config_version: int
    bootstrap_version: int
    instance_id: str
    runtime_mode: str
    bootstrap_state: str
    current_step: str | None
    last_error: str | None
    database: DatabaseState
    managed: ManagedInstanceState | None
    backups: BackupState
    embeddings: EmbeddingRuntimeState

    @property
    def machine_instance_id(self) -> str:
        """Return the active machine instance identifier."""

        return self.instance_id
