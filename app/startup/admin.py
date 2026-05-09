"""Composition helpers for human admin CLI endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.infrastructure.db.runtime import engine as db_engine
from app.infrastructure.host_apps import assets as host_assets
from app.infrastructure.host_apps.identity import claude_hook_install
from app.infrastructure.local_state import (
    machine_config_store,
    session_state_file_store,
)
from app.startup import admin_db, analytics, db as startup_db
from app.startup.host_hooks import (
    CLAUDE_SESSION_START_ENTRYPOINT_MODULE,
    CURSOR_STATUSLINE_ENTRYPOINT_MODULE,
)


def managed_backup_kwargs() -> dict[str, object]:
    """Return managed-container backup kwargs when machine config is active and readable."""

    machine_config, machine_error = machine_config_store.try_load_machine_config()
    if (
        machine_error is not None
        or machine_config is None
        or machine_config.runtime_mode != "managed_local"
        or machine_config.managed is None
    ):
        return {}
    return {
        "container_name": machine_config.managed.container_name,
        "container_db_name": machine_config.managed.db_name,
        "container_admin_user": machine_config.managed.admin_user,
        "container_admin_password": machine_config.managed.admin_password,
    }


def managed_restore_kwargs(backup_kwargs: dict[str, object]) -> dict[str, object]:
    """Trim backup kwargs down to the subset restore understands."""

    return {
        key: value
        for key, value in backup_kwargs.items()
        if key in {"container_name", "container_admin_user", "container_admin_password"}
    }


def build_admin_analytics_report(*, days: int) -> dict:
    """Build the admin analytics report using the configured database."""

    dsn = startup_db.get_optional_db_dsn() or admin_db.get_optional_admin_db_dsn()
    if not dsn:
        raise RuntimeError(
            "Shellbrain database is not configured. Run `shellbrain init` first."
        )
    return analytics.build_analytics_report(engine=db_engine.get_engine(dsn), days=days)


def install_repo_claude_hook(*, repo_root: Path) -> Path:
    """Install the repo-local Claude hook."""

    return claude_hook_install.install_claude_hook(
        repo_root=repo_root,
        session_start_module=CLAUDE_SESSION_START_ENTRYPOINT_MODULE,
    )


def install_managed_host_assets(*, host_mode: str, force: bool):
    """Install Shellbrain-managed host assets."""

    return host_assets.install_host_assets(
        host_mode=host_mode,
        force=force,
        claude_session_start_module=CLAUDE_SESSION_START_ENTRYPOINT_MODULE,
        cursor_statusline_module=CURSOR_STATUSLINE_ENTRYPOINT_MODULE,
    )


def load_session_state(*, repo_root: Path, caller_id: str):
    """Load one file-backed session state."""

    return session_state_file_store.FileSessionStateStore().load(
        repo_root=repo_root, caller_id=caller_id
    )


def delete_session_state(*, repo_root: Path, caller_id: str) -> None:
    """Delete one file-backed session state."""

    session_state_file_store.FileSessionStateStore().delete(
        repo_root=repo_root, caller_id=caller_id
    )


def gc_session_state(*, repo_root: Path) -> int:
    """Delete stale caller state files for one repo."""

    return session_state_file_store.FileSessionStateStore().gc(
        repo_root=repo_root,
        older_than_iso=(datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
    )
