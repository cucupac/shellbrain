"""Admin command implementation."""

from __future__ import annotations

import argparse
import json
import sys

from app.entrypoints.cli.handlers.human.admin_dependencies import (
    AdminCommandDependencies,
)


def run_admin_command(
    args: argparse.Namespace,
    *,
    dependencies: AdminCommandDependencies,
) -> int:
    """Execute one admin command."""

    if args.admin_command == "backup":
        admin_dsn = dependencies.get_admin_db_dsn()
        backup_root = dependencies.get_backup_dir()
        mirror_root = dependencies.get_backup_mirror_dir()
        backup_kwargs = dependencies.managed_backup_kwargs()
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

    if args.admin_command == "recall":
        try:
            dependencies.save_recall_provider(args.provider)
        except (ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Recall provider: {args.provider}")
        return 0
    raise ValueError(f"Unsupported admin command: {args.admin_command}")
