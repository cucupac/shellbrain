"""This module defines the CLI entry point for shellbrain operations and admin commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, Sequence

from app.entrypoints.cli.parser import build_parser

if TYPE_CHECKING:
    from app.startup.repo_context import RepoContext


def _load_payload(json_text: str | None, json_file: str | None) -> dict[str, Any]:
    """This function loads a payload from either inline JSON text or a JSON file."""

    if json_text:
        return json.loads(json_text)
    if json_file:
        content = Path(json_file).read_text(encoding="utf-8")
        return json.loads(content)
    raise ValueError("Either --json or --json-file is required")


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and dispatch to the requested operational or admin path."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        try:
            from app.entrypoints.cli.endpoints.human.init import (
                run as run_init_endpoint,
            )

            return run_init_endpoint(
                args,
                resolve_admin_repo_root=_resolve_admin_repo_root,
                should_register_repo=_should_register_repo_during_init,
            )
        except ValueError as exc:
            parser.error(str(exc))
            return 2

    if args.command == "upgrade":
        from app.entrypoints.cli.endpoints.human.upgrade import (
            run as run_upgrade_endpoint,
        )

        return run_upgrade_endpoint()

    if args.command == "metrics":
        return _run_metrics_command(args)

    if args.command == "admin":
        return _run_admin_command(args)

    try:
        from app.startup.repo_context import resolve_repo_context

        repo_context = resolve_repo_context(
            repo_root_arg=getattr(args, "repo_root", None),
            repo_id_arg=getattr(args, "repo_id", None),
        )
        payload = _load_payload(
            getattr(args, "json_text", None), getattr(args, "json_file", None)
        )
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    try:
        from app.startup.cli import run_operation_command

        result = run_operation_command(
            command=_operation_route_command(args),
            payload=payload,
            repo_context=repo_context,
            repo_id_override=getattr(args, "repo_id", None),
            no_sync=bool(getattr(args, "no_sync", False)),
            dispatch_operation=_dispatch_operation_command,
        )
        _print_operation_result(result)
        return 0
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _operation_route_command(args: argparse.Namespace) -> str:
    """Map parsed CLI syntax to one endpoint route key."""

    if args.command == "memory":
        return f"memory:{args.memory_command}"
    if args.command == "concept" and getattr(args, "concept_command", None):
        return f"concept:{args.concept_command}"
    return str(args.command)


def _dispatch_operation_command(
    command: str, payload: dict[str, Any], repo_context: RepoContext
) -> dict[str, Any]:
    """Resolve runtime dependencies lazily and execute one operational command."""

    kwargs = {"repo_id": repo_context.repo_id, "repo_root": repo_context.repo_root}
    if command == "recall":
        from app.entrypoints.cli.endpoints.working_agent.recall import run

        return run(payload, **kwargs)
    if command == "read":
        from app.entrypoints.cli.endpoints.internal_agent.read import run

        return run(payload, **kwargs)
    if command == "events":
        from app.entrypoints.cli.endpoints.internal_agent.events import run

        return run(payload, **kwargs)
    if command == "memory:add":
        from app.entrypoints.cli.endpoints.internal_agent.memories.add import run

        return run(payload, **kwargs)
    if command == "memory:update":
        from app.entrypoints.cli.endpoints.internal_agent.memories.update import run

        return run(payload, **kwargs)
    if command == "concept:add":
        from app.entrypoints.cli.endpoints.internal_agent.concepts.add import run

        return run(payload, **kwargs)
    if command == "concept:update":
        from app.entrypoints.cli.endpoints.internal_agent.concepts.update import run

        return run(payload, **kwargs)
    raise ValueError(f"Unsupported command: {command}")


def _run_admin_command(args: argparse.Namespace) -> int:
    """Execute one admin command."""

    from app.entrypoints.cli.endpoints.human.admin import run_admin_command
    from app.startup import admin as startup_admin

    return run_admin_command(
        args,
        resolve_admin_repo_root=_resolve_admin_repo_root,
        managed_backup_kwargs=lambda _machine_config, _machine_error: (
            startup_admin.managed_backup_kwargs()
        ),
        managed_restore_kwargs=startup_admin.managed_restore_kwargs,
    )


def _run_metrics_command(args: argparse.Namespace) -> int:
    """Generate metrics snapshots and artifacts for one or many repos."""

    from app.entrypoints.cli.endpoints.human.metrics import run_metrics_command
    from app.startup.cli import warn_or_fail_on_unsafe_app_role

    return run_metrics_command(
        args, warn_or_fail_on_unsafe_app_role=warn_or_fail_on_unsafe_app_role
    )


def _print_operation_result(result: dict[str, Any]) -> None:
    """Render one operation result as JSON for agent consumption."""

    from app.entrypoints.cli.presenters.json import render

    print(render(result))


def _resolve_admin_repo_root(repo_root_arg: str | None) -> Path:
    """Resolve one admin repo root without inferring repo_id."""

    repo_root = (
        Path(repo_root_arg).expanduser().resolve()
        if repo_root_arg
        else Path.cwd().resolve()
    )
    if not repo_root.exists():
        raise ValueError(f"repo_root does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise ValueError(f"repo_root must be a directory: {repo_root}")
    return repo_root


def _should_register_repo_during_init(
    *, repo_root: Path, repo_root_arg: str | None, repo_id_arg: str | None
) -> bool:
    """Return whether init should register one repo immediately."""

    from app.startup.cli import should_register_repo_during_init

    return should_register_repo_during_init(
        repo_root=repo_root,
        repo_root_arg=repo_root_arg,
        repo_id_arg=repo_id_arg,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
