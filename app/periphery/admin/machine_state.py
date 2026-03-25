"""Machine-owned Shellbrain runtime config and bootstrap state."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tomllib
from typing import Any

from app.boot.home import (
    get_machine_backups_dir,
    get_machine_config_path,
    get_machine_models_dir,
    get_shellbrain_home,
)


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


def default_paths() -> dict[str, str]:
    """Return default machine-owned storage paths."""

    return {
        "backups_root": str(get_machine_backups_dir()),
        "models_root": str(get_machine_models_dir()),
    }


def load_machine_config(path: Path | None = None) -> MachineConfig | None:
    """Return the parsed machine config when it exists and is valid."""

    target = path or get_machine_config_path()
    try:
        payload = tomllib.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    return _machine_config_from_payload(payload)


def try_load_machine_config(path: Path | None = None) -> tuple[MachineConfig | None, str | None]:
    """Best-effort machine-config load that reports corruption text instead of raising."""

    target = path or get_machine_config_path()
    try:
        return load_machine_config(target), None
    except (tomllib.TOMLDecodeError, ValueError) as exc:
        return None, str(exc)


def save_machine_config(config: MachineConfig, path: Path | None = None) -> Path:
    """Persist one machine config with owner-only permissions."""

    target = path or get_machine_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_render_machine_config(config), encoding="utf-8")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target


def backup_corrupt_machine_config(*, path: Path | None = None) -> Path | None:
    """Rename a corrupt config aside and return the backup path when present."""

    target = path or get_machine_config_path()
    if not target.exists():
        return None
    backup = target.with_name(f"config.corrupt.{_timestamp_slug()}.toml")
    target.replace(backup)
    return backup


def update_bootstrap_state(
    config: MachineConfig,
    *,
    bootstrap_state: str,
    current_step: str | None,
    last_error: str | None,
) -> MachineConfig:
    """Return a copy with updated bootstrap status fields."""

    return replace(
        config,
        bootstrap_state=bootstrap_state,
        current_step=current_step,
        last_error=last_error,
    )


def build_recovery_stub(*, current_step: str | None, last_error: str | None) -> dict[str, Any]:
    """Return a minimal recovery payload for config corruption cases."""

    return {
        "config_version": CONFIG_VERSION,
        "bootstrap_version": BOOTSTRAP_VERSION,
        "runtime_mode": RUNTIME_MODE_MANAGED_LOCAL,
        "bootstrap_state": BOOTSTRAP_STATE_REPAIR_NEEDED,
        "current_step": current_step,
        "last_error": last_error,
        "paths": default_paths(),
    }


def save_recovery_stub(*, current_step: str | None, last_error: str | None, path: Path | None = None) -> Path:
    """Persist a minimal repair-needed stub after config corruption."""

    target = path or get_machine_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_recovery_stub(current_step=current_step, last_error=last_error)
    target.write_text(_render_simple_payload(payload), encoding="utf-8")
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    return target


def _machine_config_from_payload(payload: dict[str, Any]) -> MachineConfig:
    """Validate and coerce a machine-config payload."""

    if not isinstance(payload, dict):
        raise ValueError("Machine config must be a TOML table.")
    database = payload.get("database")
    managed = payload.get("managed")
    backups = payload.get("backups")
    embeddings = payload.get("embeddings")
    if not isinstance(database, dict):
        raise ValueError("Machine config is missing the required database section.")
    if not isinstance(backups, dict) or not isinstance(embeddings, dict):
        raise ValueError("Machine config is missing required backups or embeddings sections.")
    runtime_mode = str(payload.get("runtime_mode") or "")
    managed_state = None
    if isinstance(managed, dict):
        managed_state = ManagedInstanceState(
            instance_id=_required_str(managed, "instance_id"),
            container_name=_required_str(managed, "container_name"),
            image=_required_str(managed, "image"),
            host=_required_str(managed, "host"),
            port=int(managed.get("port") or 0),
            db_name=_required_str(managed, "db_name"),
            data_dir=_required_str(managed, "data_dir"),
            admin_user=_required_str(managed, "admin_user"),
            admin_password=_required_str(managed, "admin_password"),
            app_user=_required_str(managed, "app_user"),
            app_password=_required_str(managed, "app_password"),
        )
    instance_id = _optional_str(payload.get("instance_id"))
    if instance_id is None and managed_state is not None:
        instance_id = managed_state.instance_id
    if instance_id is None:
        raise ValueError("Machine config is missing the required instance_id field.")
    if runtime_mode == RUNTIME_MODE_MANAGED_LOCAL and managed_state is None:
        raise ValueError("Managed-local machine config is missing the managed section.")
    if runtime_mode not in {RUNTIME_MODE_MANAGED_LOCAL, RUNTIME_MODE_EXTERNAL_POSTGRES}:
        raise ValueError(f"Unsupported machine config runtime_mode: {runtime_mode!r}")
    return MachineConfig(
        config_version=int(payload.get("config_version") or 0),
        bootstrap_version=int(payload.get("bootstrap_version") or 0),
        instance_id=instance_id,
        runtime_mode=runtime_mode,
        bootstrap_state=str(payload.get("bootstrap_state") or ""),
        current_step=_optional_str(payload.get("current_step")),
        last_error=_optional_str(payload.get("last_error")),
        database=DatabaseState(
            app_dsn=_required_str(database, "app_dsn"),
            admin_dsn=_required_str(database, "admin_dsn"),
        ),
        managed=managed_state,
        backups=BackupState(
            root=_required_str(backups, "root"),
            mirror_root=_optional_str(backups.get("mirror_root")),
        ),
        embeddings=EmbeddingRuntimeState(
            provider=_required_str(embeddings, "provider"),
            model=_required_str(embeddings, "model"),
            model_revision=_optional_str(embeddings.get("model_revision")),
            backend_version=_optional_str(embeddings.get("backend_version")),
            cache_path=_required_str(embeddings, "cache_path"),
            readiness_state=_required_str(embeddings, "readiness_state"),
            last_error=_optional_str(embeddings.get("last_error")),
        ),
    )


def _required_str(payload: dict[str, Any], key: str) -> str:
    """Return a required string field or raise."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Machine config field {key!r} must be a non-empty string.")
    return value


def _optional_str(value: Any) -> str | None:
    """Return an optional string value."""

    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Optional string fields must be strings when present.")
    return value or None


def _render_machine_config(config: MachineConfig) -> str:
    """Render one machine config to TOML."""

    payload = {
        "config_version": config.config_version,
        "bootstrap_version": config.bootstrap_version,
        "instance_id": config.instance_id,
        "runtime_mode": config.runtime_mode,
        "bootstrap_state": config.bootstrap_state,
        "current_step": config.current_step,
        "last_error": config.last_error,
        "database": {
            "app_dsn": config.database.app_dsn,
            "admin_dsn": config.database.admin_dsn,
        },
        "backups": {
            "root": config.backups.root,
            "mirror_root": config.backups.mirror_root,
        },
        "embeddings": {
            "provider": config.embeddings.provider,
            "model": config.embeddings.model,
            "model_revision": config.embeddings.model_revision,
            "backend_version": config.embeddings.backend_version,
            "cache_path": config.embeddings.cache_path,
            "readiness_state": config.embeddings.readiness_state,
            "last_error": config.embeddings.last_error,
        },
    }
    if config.managed is not None:
        payload["managed"] = {
            "instance_id": config.managed.instance_id,
            "container_name": config.managed.container_name,
            "image": config.managed.image,
            "host": config.managed.host,
            "port": config.managed.port,
            "db_name": config.managed.db_name,
            "data_dir": config.managed.data_dir,
            "admin_user": config.managed.admin_user,
            "admin_password": config.managed.admin_password,
            "app_user": config.managed.app_user,
            "app_password": config.managed.app_password,
        }
    return _render_simple_payload(payload)


def _render_simple_payload(payload: dict[str, Any]) -> str:
    """Render a limited nested mapping to TOML."""

    root_lines: list[str] = []
    section_lines: list[str] = []
    for key, value in payload.items():
        if isinstance(value, dict):
            section_lines.extend(_render_table(key, value))
        else:
            root_lines.append(f"{key} = {_toml_value(value)}")
    lines = [*root_lines]
    if root_lines and section_lines:
        lines.append("")
    lines.extend(section_lines)
    return "\n".join(lines) + "\n"


def _render_table(name: str, payload: dict[str, Any]) -> list[str]:
    """Render one TOML table."""

    lines = [f"[{name}]"]
    for key, value in payload.items():
        lines.append(f"{key} = {_toml_value(value)}")
    lines.append("")
    return lines


def _toml_value(value: Any) -> str:
    """Render one limited TOML literal."""

    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value))


def _timestamp_slug() -> str:
    """Return a filesystem-safe timestamp slug."""

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
