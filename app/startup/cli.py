"""Composition helpers for CLI entrypoints."""

from __future__ import annotations

import sys
from uuid import uuid4

from app.startup.cli_runtime import CliRuntime


def build_cli_runtime():
    """Build the concrete dependency set for the CLI runner."""

    from app.startup import create_policy
    from app.startup import episode_sync_launcher
    from app.startup import metrics as startup_metrics
    from app.startup import operation_dependencies
    from app.startup import read_policy
    from app.startup import repo_context
    from app.startup import runtime_admin
    from app.startup import runtime_context as startup_runtime_context
    from app.startup import snapshot_baseline
    from app.startup import use_cases
    from app.startup import wiki as startup_wiki
    from app.infrastructure.local_state import operation_registration
    from app.infrastructure.process.episode_sync import autostart as episode_autostart
    from app.infrastructure.telemetry import operation_polling

    return CliRuntime(
        resolve_repo_context=repo_context.resolve_repo_context,
        build_operation_dependencies=operation_dependencies.build_operation_dependencies,
        get_create_hydration_defaults=create_policy.get_create_hydration_defaults,
        get_read_hydration_defaults=read_policy.get_read_hydration_defaults,
        get_uow_factory=use_cases.get_uow_factory,
        get_embedding_provider_factory=use_cases.get_embedding_provider_factory,
        get_embedding_model=use_cases.get_embedding_model,
        get_operation_telemetry_context=(
            startup_runtime_context.get_operation_telemetry_context
        ),
        new_invocation_id=lambda: str(uuid4()),
        resolve_caller_identity=resolve_cli_caller_identity,
        set_operation_context=set_cli_operation_context,
        reset_operation_context=reset_cli_operation_context,
        ensure_repo_registration=(
            operation_registration.ensure_repo_registration_for_operation
        ),
        ensure_shadow_baseline=snapshot_baseline.ensure_shadow_baseline_for_operation,
        maybe_start_sync=lambda repo_context_value: episode_autostart.maybe_start_sync(
            repo_context_value,
            ensure_episode_sync_started=(
                episode_sync_launcher.ensure_episode_sync_started
            ),
        ),
        update_operation_polling_status=lambda **kwargs: (
            operation_polling.update_operation_polling_status(
                uow_factory=use_cases.get_uow_factory(), **kwargs
            )
        ),
        should_register_repo_during_init=(
            operation_registration.should_register_repo_during_init
        ),
        run_init=runtime_admin.run_init,
        init_success_presenter_context=runtime_admin.init_success_presenter_context,
        run_upgrade_command=run_upgrade_command,
        warn_or_fail_on_unsafe_app_role=warn_or_fail_on_unsafe_app_role,
        run_metrics_dashboard=startup_metrics.run_metrics_dashboard,
        run_wiki=startup_wiki.run_wiki,
        admin_dependencies=build_admin_command_dependencies(),
    )


def build_admin_command_dependencies():
    """Build concrete dependencies for human admin CLI commands."""

    from app.startup import admin as startup_admin
    from app.startup import admin_db
    from app.startup import admin_diagnose
    from app.startup import backup as startup_backup
    from app.startup import db as startup_db
    from app.startup import migrations
    from app.startup import model_usage_backfill
    from app.startup.admin_dependencies import AdminCommandDependencies

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

    from app.infrastructure.system import package_upgrade as runtime_upgrade

    return runtime_upgrade.run_upgrade()


def resolve_cli_caller_identity():
    """Resolve caller identity through concrete host adapters."""

    from app.infrastructure.host_apps.identity import resolver as host_identity_resolver

    return host_identity_resolver.resolve_caller_identity()


def set_cli_operation_context(context):
    """Set the operation telemetry context for one CLI invocation."""

    from app.startup import runtime_context as startup_runtime_context

    return startup_runtime_context.set_operation_telemetry_context(context)


def reset_cli_operation_context(token) -> None:
    """Reset one CLI operation telemetry context token."""

    from app.startup import runtime_context as startup_runtime_context

    startup_runtime_context.reset_operation_telemetry_context(token)


def warn_or_fail_on_unsafe_app_role() -> None:
    """Run the concrete app-role safety check."""

    from app.infrastructure.db.admin.app_role_safety import (
        warn_or_fail_on_unsafe_app_role as warn_or_fail,
    )
    from app.startup import admin_db
    from app.startup import db as startup_db

    warn_or_fail(
        get_db_dsn=startup_db.get_db_dsn,
        should_fail_on_unsafe_app_role=admin_db.should_fail_on_unsafe_app_role,
        stderr=sys.stderr,
    )
