"""Admin command implementation."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import json
from pathlib import Path
import sys
from typing import Any


def run_admin_command(
    args: argparse.Namespace,
    *,
    resolve_admin_repo_root: Callable[[str | None], Path],
    managed_backup_kwargs: Callable[[object, str | None], dict[str, Any]],
    managed_restore_kwargs: Callable[[dict[str, Any]], dict[str, Any]],
) -> int:
    """Execute one admin command."""

    if args.admin_command == "migrate":
        from app.startup.migrations import DatabaseRevisionAheadOfInstalledPackageError, upgrade_database

        try:
            upgrade_database()
        except DatabaseRevisionAheadOfInstalledPackageError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print("Applied shellbrain schema migrations to head.")
        return 0

    if args.admin_command == "backup":
        from app.startup.admin_db import get_admin_db_dsn, get_backup_dir, get_backup_mirror_dir
        from app.startup.admin import managed_backup_kwargs as build_managed_backup_kwargs
        from app.startup.backup import create_backup, list_backups, restore_backup, verify_backup
        from app.startup.db import get_optional_db_dsn

        admin_dsn = get_admin_db_dsn()
        backup_root = get_backup_dir()
        mirror_root = get_backup_mirror_dir()
        backup_kwargs = managed_backup_kwargs(None, None) or build_managed_backup_kwargs()
        subcommand = getattr(args, "backup_command", None)
        if subcommand == "create":
            manifest = create_backup(admin_dsn=admin_dsn, backup_root=backup_root, mirror_root=mirror_root, **backup_kwargs)
            print(json.dumps(manifest.__dict__, indent=2, sort_keys=True))
            return 0
        if subcommand == "list":
            print(json.dumps([manifest.__dict__ for manifest in list_backups(backup_root=backup_root)], indent=2, sort_keys=True))
            return 0
        if subcommand == "verify":
            manifest = verify_backup(backup_root=backup_root, backup_id=args.backup_id)
            print(json.dumps(manifest.__dict__, indent=2, sort_keys=True))
            return 0
        if subcommand == "restore":
            manifest = restore_backup(
                admin_dsn=admin_dsn,
                backup_root=backup_root,
                target_db=args.target_db,
                app_dsn=get_optional_db_dsn(),
                backup_id=args.backup_id,
                **managed_restore_kwargs(backup_kwargs),
            )
            print(json.dumps({"restored_backup_id": manifest.backup_id, "target_db": args.target_db}, indent=2, sort_keys=True))
            return 0

    if args.admin_command == "doctor":
        from app.startup.admin_db import get_backup_dir, get_optional_admin_db_dsn
        from app.startup.admin_doctor import build_doctor_report
        from app.startup.db import get_optional_db_dsn

        report = build_doctor_report(
            app_dsn=get_optional_db_dsn(),
            admin_dsn=get_optional_admin_db_dsn(),
            backup_root=get_backup_dir(),
            repo_root=resolve_admin_repo_root(getattr(args, "repo_root", None)),
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    if args.admin_command == "analytics":
        from app.startup.admin import build_admin_analytics_report

        report = build_admin_analytics_report(days=int(args.days))
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    if args.admin_command == "backfill-token-usage":
        from app.startup.db import get_engine_instance
        from app.startup.model_usage_backfill import backfill_model_usage

        summary = backfill_model_usage(engine=get_engine_instance())
        print(json.dumps(summary.to_payload(), indent=2, sort_keys=True))
        return 0

    repo_root = resolve_admin_repo_root(getattr(args, "repo_root", None))
    if args.admin_command == "install-claude-hook":
        from app.startup.admin import install_repo_claude_hook

        settings_path = install_repo_claude_hook(repo_root=repo_root)
        print(f"Installed Claude hook at {settings_path}")
        return 0
    if args.admin_command == "install-host-assets":
        from app.startup.admin import install_managed_host_assets

        result = install_managed_host_assets(host_mode=args.host, force=bool(args.force))
        for line in result.lines:
            print(line)
        return 0
    if args.admin_command == "session-state":
        from app.startup.admin import delete_session_state, gc_session_state, load_session_state

        subcommand = getattr(args, "session_state_command", None)
        if subcommand == "inspect":
            state = load_session_state(repo_root=repo_root, caller_id=args.caller_id)
            print(json.dumps(None if state is None else state.__dict__, indent=2, sort_keys=True))
            return 0
        if subcommand == "clear":
            delete_session_state(repo_root=repo_root, caller_id=args.caller_id)
            print(f"Cleared session state for {args.caller_id}")
            return 0
        if subcommand == "gc":
            deleted = gc_session_state(repo_root=repo_root)
            print(json.dumps({"deleted": deleted}, indent=2, sort_keys=True))
            return 0
    raise ValueError(f"Unsupported admin command: {args.admin_command}")
