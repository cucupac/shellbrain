"""Composition helpers for CLI entrypoints."""

from __future__ import annotations

from pathlib import Path
import sys

from app.infrastructure.host_identity import resolver as host_identity_resolver
from app.infrastructure.local_state import machine_config_store, repo_registration_store
from app.infrastructure.postgres_admin import instance_guard
from app.infrastructure.runtime import upgrade as runtime_upgrade
from app.startup import admin_db
from app.startup import db as startup_db
from app.startup import runtime_context as startup_runtime_context


def run_upgrade_command() -> int:
    """Run the hosted package upgrader."""

    return runtime_upgrade.run_upgrade()


def resolve_cli_caller_identity():
    """Resolve caller identity through concrete host adapters."""

    return host_identity_resolver.resolve_caller_identity()


def set_cli_operation_context(context):
    """Set the operation telemetry context for one CLI invocation."""

    return startup_runtime_context.set_operation_telemetry_context(context)


def reset_cli_operation_context(token) -> None:
    """Reset one CLI operation telemetry context token."""

    startup_runtime_context.reset_operation_telemetry_context(token)


def should_register_repo_during_init(*, repo_root: Path, repo_root_arg: str | None, repo_id_arg: str | None) -> bool:
    """Return whether init should register one repo immediately."""

    if repo_root_arg is not None or repo_id_arg is not None:
        return True
    if repo_registration_store.resolve_git_root(repo_root) is not None:
        return True
    return repo_registration_store.load_repo_registration_for_target(repo_root) is not None


def ensure_repo_registration_for_operation(*, registration_root: Path | None, repo_id_override: str | None) -> None:
    """Best-effort auto-registration of one repo before a Shellbrain operation."""

    if registration_root is None:
        return
    try:
        machine_config, machine_error = machine_config_store.try_load_machine_config()
        if machine_error is not None or machine_config is None:
            return
        repo_registration_store.register_repo_for_target(
            repo_root=registration_root,
            machine_instance_id=machine_config.machine_instance_id,
            explicit_repo_id=repo_id_override,
        )
    except Exception:
        return


def warn_or_fail_on_unsafe_app_role() -> None:
    """Emit one warning, or fail in strict mode, when the app DSN is overprivileged."""

    dsn = startup_db.get_db_dsn()
    warnings = instance_guard.inspect_role_safety(dsn)
    if not warnings:
        return
    message = "Unsafe Shellbrain app-role configuration:\n- " + "\n- ".join(warnings)
    metadata = instance_guard.fetch_instance_metadata(dsn)
    if metadata is not None and metadata.instance_mode in {instance_guard.TEST, instance_guard.SCRATCH}:
        print(message, file=sys.stderr)
        return
    if admin_db.should_fail_on_unsafe_app_role():
        raise ValueError(message)
    print(message, file=sys.stderr)
