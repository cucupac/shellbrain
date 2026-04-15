"""Operational diagnostics for Shellbrain safety posture."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

import psycopg

from app.boot.home import get_shellbrain_home
from app.periphery.admin import external_runtime
from app.periphery.admin.backup import list_backups
from app.periphery.admin.instance_guard import fetch_instance_metadata, fingerprint_summary, inspect_role_safety
from app.periphery.admin.machine_state import (
    MachineConfig,
    RUNTIME_MODE_EXTERNAL_POSTGRES,
    RUNTIME_MODE_MANAGED_LOCAL,
    try_load_machine_config,
)
from app.periphery.admin.repo_state import IDENTITY_STRENGTH_WEAK_LOCAL, load_repo_registration_for_target, resolve_git_root
from app.periphery.onboarding.host_assets import inspect_host_assets

_LOW_DISK_WARNING_BYTES = 2 * 1024 * 1024 * 1024


def build_doctor_report(
    *,
    app_dsn: str | None,
    admin_dsn: str | None,
    backup_root: Path,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Return one structured safety report for the current Shellbrain environment."""

    machine_config, machine_error = try_load_machine_config()
    instance = None
    if app_dsn:
        instance = fetch_instance_metadata(app_dsn)
    if instance is None and admin_dsn:
        instance = fetch_instance_metadata(admin_dsn)
    backups = list_backups(backup_root=backup_root)
    app_role_warnings = [] if not app_dsn else inspect_role_safety(app_dsn)
    admin_role_warnings = [] if not admin_dsn else inspect_role_safety(admin_dsn)
    checked_at = datetime.now(timezone.utc)
    latest_backup = None if not backups else json.loads(json.dumps(backups[0].__dict__))
    backup_age_seconds = None
    if backups:
        created_at = datetime.fromisoformat(backups[0].created_at.replace("Z", "+00:00"))
        backup_age_seconds = int((checked_at - created_at.astimezone(timezone.utc)).total_seconds())
    home_root = get_shellbrain_home()
    disk = shutil.disk_usage(home_root if home_root.exists() else home_root.parent)
    repo_report = _build_repo_report(repo_root=repo_root)
    host_integrations = inspect_host_assets()
    cursor_statusline = getattr(
        host_integrations,
        "cursor_statusline",
        {
            "installed": False,
            "managed": False,
            "malformed": False,
            "path": None,
            "command_executable": None,
            "executable_exists": None,
        },
    )
    runtime_warnings = _runtime_warnings(machine_config)

    report: dict[str, Any] = {
        "checked_at": checked_at.isoformat(),
        "shellbrain_home": str(home_root),
        "config_status": _config_status(machine_config=machine_config, machine_error=machine_error),
        "config_error": machine_error,
        "runtime_mode": None if machine_config is None else machine_config.runtime_mode,
        "bootstrap_state": None if machine_config is None else machine_config.bootstrap_state,
        "current_step": None if machine_config is None else machine_config.current_step,
        "last_error": None if machine_config is None else machine_config.last_error,
        "config_version": None if machine_config is None else machine_config.config_version,
        "bootstrap_version": None if machine_config is None else machine_config.bootstrap_version,
        "machine_instance": _machine_instance_report(machine_config),
        "runtime_warnings": runtime_warnings,
        "effective_config": _effective_config_summary(machine_config=machine_config, app_dsn=app_dsn, admin_dsn=admin_dsn),
        "app_dsn_configured": bool(app_dsn),
        "admin_dsn_configured": bool(admin_dsn),
        "instance": None if instance is None else instance.__dict__,
        "app_role_warnings": app_role_warnings,
        "admin_role_warnings": admin_role_warnings,
        "schema_revision": None if not app_dsn else _fetch_schema_revision(app_dsn),
        "backup_root": str(backup_root),
        "backup_count": len(backups),
        "latest_backup": latest_backup,
        "backup_age_seconds": backup_age_seconds,
        "disk_free_bytes": disk.free,
        "disk_warning": None if disk.free >= _LOW_DISK_WARNING_BYTES else "Low free disk space under Shellbrain home.",
        "host_integrations": {
            "codex_startup_guidance": host_integrations.codex_startup_guidance,
            "codex_skill": host_integrations.codex_skill,
            "claude_startup_guidance": host_integrations.claude_startup_guidance,
            "claude_skill": host_integrations.claude_skill,
            "cursor_skill": host_integrations.cursor_skill,
            "cursor_statusline": cursor_statusline,
            "claude_global_hook": host_integrations.claude_global_hook,
        },
        "repo": repo_report,
    }
    if repo_report and repo_report.get("identity_strength") == IDENTITY_STRENGTH_WEAK_LOCAL:
        report["repo_warning"] = "Repo identity is weak-local and will change if this directory moves."
    claude_hook = report["host_integrations"]["claude_global_hook"]
    if claude_hook.get("managed") and not claude_hook.get("executable_exists", False):
        report["host_integration_warning"] = (
            "Claude global hook points at a missing interpreter. Rerun `shellbrain init` to repair it."
        )
    return report


def _build_repo_report(*, repo_root: Path | None) -> dict[str, Any] | None:
    """Return repo-local registration status when the target looks repo-shaped."""

    if repo_root is None:
        return None
    target = Path(repo_root).expanduser().resolve()
    git_root = resolve_git_root(target)
    registration = load_repo_registration_for_target(target)
    if registration is None and git_root is None and not (target / ".shellbrain").exists():
        return None
    return {
        "repo_root": str(target),
        "git_root": str(git_root) if git_root is not None else None,
        "registered": registration is not None,
        "repo_id": None if registration is None else registration.repo_id,
        "identity_strength": None if registration is None else registration.identity_strength,
        "source_remote": None if registration is None else registration.source_remote,
        "machine_instance_id": None if registration is None else registration.machine_instance_id,
        "registered_at": None if registration is None else registration.registered_at,
        "claude_status": None if registration is None else registration.claude_status,
        "claude_settings_path": None if registration is None else registration.claude_settings_path,
        "claude_note": None if registration is None else registration.claude_note,
    }


def _config_status(*, machine_config: MachineConfig | None, machine_error: str | None) -> str:
    """Return one short machine config health label."""

    if machine_error:
        return "corrupt"
    if machine_config is not None:
        return "ok"
    return "absent"


def _machine_instance_report(machine_config: MachineConfig | None) -> dict[str, Any] | None:
    """Return runtime details when machine config exists."""

    if machine_config is None:
        return None
    report: dict[str, Any] = {
        "instance_id": machine_config.machine_instance_id,
        "runtime_mode": machine_config.runtime_mode,
        "backup_root": machine_config.backups.root,
        "embeddings": {
            "provider": machine_config.embeddings.provider,
            "model": machine_config.embeddings.model,
            "model_revision": machine_config.embeddings.model_revision,
            "backend_version": machine_config.embeddings.backend_version,
            "cache_path": machine_config.embeddings.cache_path,
            "readiness_state": machine_config.embeddings.readiness_state,
            "last_error": machine_config.embeddings.last_error,
        },
    }
    if machine_config.runtime_mode == RUNTIME_MODE_MANAGED_LOCAL and machine_config.managed is not None:
        report.update(
            {
                "container_name": machine_config.managed.container_name,
                "image": machine_config.managed.image,
                "host": machine_config.managed.host,
                "port": machine_config.managed.port,
                "db_name": machine_config.managed.db_name,
                "data_dir": machine_config.managed.data_dir,
            }
        )
        return report
    if machine_config.runtime_mode == RUNTIME_MODE_EXTERNAL_POSTGRES:
        report["database"] = fingerprint_summary(machine_config.database.admin_dsn)
    return report


def _runtime_warnings(machine_config: MachineConfig | None) -> list[str]:
    """Return runtime-specific warnings for the active machine config."""

    if machine_config is None:
        return []
    if machine_config.runtime_mode == RUNTIME_MODE_EXTERNAL_POSTGRES:
        return external_runtime.inspect_runtime(admin_dsn=machine_config.database.admin_dsn)
    return []


def _effective_config_summary(
    *,
    machine_config: MachineConfig | None,
    app_dsn: str | None,
    admin_dsn: str | None,
) -> dict[str, Any]:
    """Return a redacted summary of the effective runtime config."""

    if machine_config is not None:
        return {
            "source": "machine_config",
            "app_dsn": _redact_dsn(machine_config.database.app_dsn),
            "admin_dsn": _redact_dsn(machine_config.database.admin_dsn),
            "runtime_mode": machine_config.runtime_mode,
            "backup_root": machine_config.backups.root,
        }
    return {
        "source": "legacy_env",
        "app_dsn": _redact_dsn(app_dsn),
        "admin_dsn": _redact_dsn(admin_dsn),
        "runtime_mode": None,
        "backup_root": None,
    }


def _redact_dsn(dsn: str | None) -> str | None:
    """Return a redacted DSN for diagnostics."""

    if not dsn:
        return None
    raw = dsn.replace("+psycopg", "")
    prefix, at_sign, host_part = raw.rpartition("@")
    if not at_sign:
        return "<redacted>"
    user_prefix, _, _ = prefix.partition("://")
    scheme = prefix.split("://", 1)[0]
    return f"{scheme}://<redacted>@{host_part}"


def _fetch_schema_revision(dsn: str) -> str | None:
    """Best-effort read of the current alembic revision."""

    try:
        with psycopg.connect(dsn.replace("+psycopg", "")) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version_num FROM alembic_version")
                return str(cur.fetchone()[0])
    except psycopg.Error:
        return None
