"""Composition helpers for CLI entrypoints."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

from app.handlers.cli_operation import CliOperationEffects, run_cli_operation
from app.infrastructure.host_identity import resolver as host_identity_resolver
from app.infrastructure.local_state import machine_config_store, repo_registration_store
from app.infrastructure.postgres_admin import instance_guard
from app.infrastructure.runtime import upgrade as runtime_upgrade
from app.startup import admin_db
from app.startup import db as startup_db
from app.startup import episode_sync_launcher
from app.startup import runtime_context as startup_runtime_context
from app.startup import use_cases


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


def run_operation_command(
    *,
    command: str,
    payload: dict[str, Any],
    repo_context,
    repo_id_override: str | None,
    no_sync: bool,
    dispatch_operation,
) -> dict[str, Any]:
    """Run one hydrated CLI operation with concrete startup side effects."""

    return run_cli_operation(
        command=command,
        payload=payload,
        repo_context=repo_context,
        repo_id_override=repo_id_override,
        no_sync=no_sync,
        dispatch_operation=dispatch_operation,
        effects=CliOperationEffects(
            new_invocation_id=lambda: str(uuid4()),
            resolve_caller_identity=resolve_cli_caller_identity,
            set_operation_context=set_cli_operation_context,
            reset_operation_context=reset_cli_operation_context,
            warn_or_fail_on_unsafe_app_role=warn_or_fail_on_unsafe_app_role,
            ensure_repo_registration=ensure_repo_registration_for_operation,
            maybe_start_sync=maybe_start_sync,
            update_operation_polling_status=update_operation_polling_status,
        ),
    )


def should_register_repo_during_init(
    *, repo_root: Path, repo_root_arg: str | None, repo_id_arg: str | None
) -> bool:
    """Return whether init should register one repo immediately."""

    if repo_root_arg is not None or repo_id_arg is not None:
        return True
    if repo_registration_store.resolve_git_root(repo_root) is not None:
        return True
    return (
        repo_registration_store.load_repo_registration_for_target(repo_root) is not None
    )


def ensure_repo_registration_for_operation(
    *,
    repo_context=None,
    registration_root: Path | None = None,
    repo_id_override: str | None,
) -> None:
    """Best-effort auto-registration of one repo before a Shellbrain operation."""

    if repo_context is not None:
        registration_root = repo_context.registration_root
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
    if metadata is not None and metadata.instance_mode in {
        instance_guard.TEST,
        instance_guard.SCRATCH,
    }:
        print(message, file=sys.stderr)
        return
    if admin_db.should_fail_on_unsafe_app_role():
        raise ValueError(message)
    print(message, file=sys.stderr)


def maybe_start_sync(repo_context) -> bool:
    """Best-effort startup for repo-local episode sync after a successful command."""

    try:
        return bool(
            episode_sync_launcher.ensure_episode_sync_started(
                repo_id=repo_context.repo_id,
                repo_root=repo_context.repo_root,
            )
        )
    except Exception:
        return False


def update_operation_polling_status(
    *, invocation_id: str, attempted: bool, started: bool
) -> None:
    """Patch poller-start telemetry flags without affecting the visible command result."""

    try:
        with use_cases.get_uow_factory()() as uow:
            uow.telemetry.update_operation_polling(
                invocation_id,
                attempted=attempted,
                started=started,
            )
    except Exception:
        return
