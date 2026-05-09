"""Composition helpers for CLI entrypoints."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Sequence
from uuid import uuid4

from app.infrastructure.cli.runner import main as run_cli_runner


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI using startup-composed concrete dependencies."""

    return run_cli_runner(argv, runtime_factory=build_cli_runtime)


def build_cli_runtime():
    """Build the concrete dependency set for the CLI runner."""

    from app.infrastructure.cli.runner import CliRuntime
    from app.startup import cli_handlers
    from app.startup import create_policy
    from app.startup import metrics as startup_metrics
    from app.startup import read_policy
    from app.startup import repo_context
    from app.startup import runtime_admin
    from app.startup import runtime_context as startup_runtime_context
    from app.startup import use_cases

    return CliRuntime(
        resolve_repo_context=repo_context.resolve_repo_context,
        run_operation_command=run_operation_command,
        get_create_hydration_defaults=create_policy.get_create_hydration_defaults,
        get_read_hydration_defaults=read_policy.get_read_hydration_defaults,
        get_uow_factory=use_cases.get_uow_factory,
        get_embedding_provider_factory=use_cases.get_embedding_provider_factory,
        get_embedding_model=use_cases.get_embedding_model,
        get_operation_telemetry_context=(
            startup_runtime_context.get_operation_telemetry_context
        ),
        handle_memory_add=cli_handlers.handle_memory_add,
        handle_update=cli_handlers.handle_update,
        handle_read=cli_handlers.handle_read,
        handle_recall=cli_handlers.handle_recall,
        handle_events=cli_handlers.handle_events,
        handle_concept_add=cli_handlers.handle_concept_add,
        handle_concept_update=cli_handlers.handle_concept_update,
        should_register_repo_during_init=should_register_repo_during_init,
        run_init=runtime_admin.run_init,
        init_success_presenter_context=runtime_admin.init_success_presenter_context,
        run_upgrade_command=run_upgrade_command,
        warn_or_fail_on_unsafe_app_role=warn_or_fail_on_unsafe_app_role,
        run_metrics_dashboard=startup_metrics.run_metrics_dashboard,
        admin_dependencies=build_admin_command_dependencies(),
    )


def build_admin_command_dependencies():
    """Build concrete dependencies for human admin CLI commands."""

    from app.infrastructure.cli.handlers.human.admin import AdminCommandDependencies
    from app.startup import admin as startup_admin
    from app.startup import admin_db
    from app.startup import admin_diagnose
    from app.startup import backup as startup_backup
    from app.startup import db as startup_db
    from app.startup import migrations
    from app.startup import model_usage_backfill

    return AdminCommandDependencies(
        upgrade_database=migrations.upgrade_database,
        migration_conflict_error=migrations.DatabaseMigrationConflictError,
        get_admin_db_dsn=admin_db.get_admin_db_dsn,
        get_optional_admin_db_dsn=admin_db.get_optional_admin_db_dsn,
        get_optional_db_dsn=startup_db.get_optional_db_dsn,
        get_engine_instance=startup_db.get_engine_instance,
        get_backup_dir=admin_db.get_backup_dir,
        get_backup_mirror_dir=admin_db.get_backup_mirror_dir,
        managed_backup_kwargs=lambda _machine_config, _machine_error: (
            startup_admin.managed_backup_kwargs()
        ),
        managed_restore_kwargs=startup_admin.managed_restore_kwargs,
        create_backup=startup_backup.create_backup,
        list_backups=startup_backup.list_backups,
        verify_backup=startup_backup.verify_backup,
        restore_backup=startup_backup.restore_backup,
        build_doctor_report=admin_diagnose.build_doctor_report,
        build_admin_analytics_report=startup_admin.build_admin_analytics_report,
        backfill_model_usage=model_usage_backfill.backfill_model_usage,
        install_repo_claude_hook=startup_admin.install_repo_claude_hook,
        install_managed_host_assets=startup_admin.install_managed_host_assets,
        load_session_state=startup_admin.load_session_state,
        delete_session_state=startup_admin.delete_session_state,
        gc_session_state=startup_admin.gc_session_state,
    )


def run_upgrade_command() -> int:
    """Run the hosted package upgrader."""

    from app.infrastructure.runtime import upgrade as runtime_upgrade

    return runtime_upgrade.run_upgrade()


def resolve_cli_caller_identity():
    """Resolve caller identity through concrete host adapters."""

    from app.infrastructure.host_identity import resolver as host_identity_resolver

    return host_identity_resolver.resolve_caller_identity()


def set_cli_operation_context(context):
    """Set the operation telemetry context for one CLI invocation."""

    from app.startup import runtime_context as startup_runtime_context

    return startup_runtime_context.set_operation_telemetry_context(context)


def reset_cli_operation_context(token) -> None:
    """Reset one CLI operation telemetry context token."""

    from app.startup import runtime_context as startup_runtime_context

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

    from app.infrastructure.cli.handlers.cli_operation import (
        CliOperationEffects,
        run_cli_operation,
    )

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

    from app.infrastructure.local_state import repo_registration_store

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

    from app.infrastructure.local_state import (
        machine_config_store,
        repo_registration_store,
    )

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

    from app.infrastructure.postgres_admin import instance_guard
    from app.startup import admin_db
    from app.startup import db as startup_db

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

    from app.startup import episode_sync_launcher

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

    from app.startup import use_cases

    try:
        with use_cases.get_uow_factory()() as uow:
            uow.telemetry.update_operation_polling(
                invocation_id,
                attempted=attempted,
                started=started,
            )
    except Exception:
        return
