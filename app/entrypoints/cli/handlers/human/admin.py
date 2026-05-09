"""Admin command implementation."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any


@dataclass(frozen=True)
class AdminCommandDependencies:
    """Startup-provided concrete behavior for admin CLI commands."""

    upgrade_database: Callable[[], None]
    migration_conflict_error: type[Exception]
    get_admin_db_dsn: Callable[[], str]
    get_optional_admin_db_dsn: Callable[[], str | None]
    get_optional_db_dsn: Callable[[], str | None]
    get_engine_instance: Callable[[], Any]
    get_backup_dir: Callable[[], Path]
    get_backup_mirror_dir: Callable[[], Path | None]
    managed_backup_kwargs: Callable[[object, str | None], dict[str, Any]]
    managed_restore_kwargs: Callable[[dict[str, Any]], dict[str, Any]]
    create_backup: Callable[..., Any]
    list_backups: Callable[..., list[Any]]
    verify_backup: Callable[..., Any]
    restore_backup: Callable[..., Any]
    build_doctor_report: Callable[..., Any]
    build_admin_analytics_report: Callable[..., Any]
    backfill_model_usage: Callable[..., Any]
    install_repo_claude_hook: Callable[..., Any]
    install_managed_host_assets: Callable[..., Any]
    load_session_state: Callable[..., Any]
    delete_session_state: Callable[..., Any]
    gc_session_state: Callable[..., Any]


def run_admin_command(
    args: argparse.Namespace,
    *,
    resolve_admin_repo_root: Callable[[str | None], Path],
    dependencies: AdminCommandDependencies,
) -> int:
    """Execute one admin command."""

    if args.admin_command == "migrate":
        try:
            dependencies.upgrade_database()
        except dependencies.migration_conflict_error as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print("Applied shellbrain schema migrations to head.")
        return 0

    if args.admin_command == "backup":
        admin_dsn = dependencies.get_admin_db_dsn()
        backup_root = dependencies.get_backup_dir()
        mirror_root = dependencies.get_backup_mirror_dir()
        backup_kwargs = dependencies.managed_backup_kwargs(None, None)
        subcommand = getattr(args, "backup_command", None)
        if subcommand == "create":
            manifest = dependencies.create_backup(
                admin_dsn=admin_dsn,
                backup_root=backup_root,
                mirror_root=mirror_root,
                **backup_kwargs,
            )
            print(json.dumps(manifest.__dict__, indent=2, sort_keys=True))
            return 0
        if subcommand == "list":
            print(
                json.dumps(
                    [
                        manifest.__dict__
                        for manifest in dependencies.list_backups(
                            backup_root=backup_root
                        )
                    ],
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if subcommand == "verify":
            manifest = dependencies.verify_backup(
                backup_root=backup_root, backup_id=args.backup_id
            )
            print(json.dumps(manifest.__dict__, indent=2, sort_keys=True))
            return 0
        if subcommand == "restore":
            manifest = dependencies.restore_backup(
                admin_dsn=admin_dsn,
                backup_root=backup_root,
                target_db=args.target_db,
                app_dsn=dependencies.get_optional_db_dsn(),
                backup_id=args.backup_id,
                **dependencies.managed_restore_kwargs(backup_kwargs),
            )
            print(
                json.dumps(
                    {
                        "restored_backup_id": manifest.backup_id,
                        "target_db": args.target_db,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0

    if args.admin_command == "doctor":
        report = dependencies.build_doctor_report(
            app_dsn=dependencies.get_optional_db_dsn(),
            admin_dsn=dependencies.get_optional_admin_db_dsn(),
            backup_root=dependencies.get_backup_dir(),
            repo_root=resolve_admin_repo_root(getattr(args, "repo_root", None)),
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    if args.admin_command == "analytics":
        report = dependencies.build_admin_analytics_report(days=int(args.days))
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    if args.admin_command == "backfill-token-usage":
        summary = dependencies.backfill_model_usage(
            engine=dependencies.get_engine_instance()
        )
        print(json.dumps(summary.to_payload(), indent=2, sort_keys=True))
        return 0

    repo_root = resolve_admin_repo_root(getattr(args, "repo_root", None))
    if args.admin_command == "install-claude-hook":
        settings_path = dependencies.install_repo_claude_hook(repo_root=repo_root)
        print(f"Installed Claude hook at {settings_path}")
        return 0
    if args.admin_command == "install-host-assets":
        result = dependencies.install_managed_host_assets(
            host_mode=args.host, force=bool(args.force)
        )
        for line in result.lines:
            print(line)
        return 0
    if args.admin_command == "session-state":
        subcommand = getattr(args, "session_state_command", None)
        if subcommand == "inspect":
            state = dependencies.load_session_state(
                repo_root=repo_root, caller_id=args.caller_id
            )
            print(
                json.dumps(
                    None if state is None else state.__dict__, indent=2, sort_keys=True
                )
            )
            return 0
        if subcommand == "clear":
            dependencies.delete_session_state(
                repo_root=repo_root, caller_id=args.caller_id
            )
            print(f"Cleared session state for {args.caller_id}")
            return 0
        if subcommand == "gc":
            deleted = dependencies.gc_session_state(repo_root=repo_root)
            print(json.dumps({"deleted": deleted}, indent=2, sort_keys=True))
            return 0
    raise ValueError(f"Unsupported admin command: {args.admin_command}")
