"""This module defines the CLI entry point for shellbrain operations and admin commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from textwrap import dedent
from typing import Any, Sequence

from shellbrain.periphery.cli.hydration import RepoContext, resolve_repo_context


class _HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Keep multiline examples readable in CLI help output."""


_TOP_LEVEL_HELP = dedent(
    """\
    Use Shellbrain for repo-scoped recall with explicit evidence.

    Typical workflow:
      1. `read` when you need prior repo context.
      2. `events` before every write so you can inspect recent `episode_event` ids.
      3. `create` or an evidence-bearing `update` with concrete `evidence_refs`. Never invent `evidence_refs`.

    Prerequisites:
      - Install the package (`pip install -e .` or `pip install git+file:///...`).
      - Set `SHELLBRAIN_DB_DSN`.
      - Run `shellbrain admin migrate` once against the target database.

    Examples:
      shellbrain read --json '{"query":"what deployment issue should I remember?"}'
      shellbrain events --json '{}'
      shellbrain create --json '{"memory":{"text":"Prod deploy failed on missing env var","kind":"problem","evidence_refs":["evt-123"]}}'
      shellbrain update --json '{"memory_id":"mem-123","update":{"type":"association_link","to_memory_id":"mem-456","relation_type":"associated_with","evidence_refs":["evt-123"]}}'
      shellbrain admin migrate

    Common recovery steps:
      - `SHELLBRAIN_DB_DSN is not set`: export the database DSN before running the CLI.
      - No active host session found: verify Codex/Claude Code transcript availability, then rerun `events`.
      - Evidence ref rejected: rerun `events` and use the returned `episode_event` ids verbatim.
      - Wrong working tree: rerun with `--repo-root` (and optionally `--repo-id`) for the target repo.

    Successful operational commands start the repo-local episode sync poller by default.
    Use `--no-sync` to suppress poller startup and `.shellbrain` runtime artifacts.
    """
)

_CREATE_HELP = dedent(
    """\
    Create one durable Shellbrain entry from explicit evidence.

    Example:
      shellbrain create --json '{"memory":{"text":"The staging DB migration needs a lock timeout","kind":"problem","evidence_refs":["evt-123"]}}'
    """
)

_READ_HELP = dedent(
    """\
    Retrieve Shellbrain context without mutating state.

    Example:
      shellbrain read --json '{"query":"what do we know about the migration lock timeout?"}'
    """
)

_EVENTS_HELP = dedent(
    """\
    Inspect the newest repo-matching host session and return recent `episode_event` ids.

    Example:
      shellbrain events --json '{"limit":10}'
    """
)

_UPDATE_HELP = dedent(
    """\
    Update one existing Shellbrain entry.

    Example:
      shellbrain update --json '{"memory_id":"mem-123","update":{"type":"association_link","to_memory_id":"mem-456","relation_type":"associated_with","evidence_refs":["evt-456"]}}'
    """
)

_ADMIN_HELP = dedent(
    """\
    Administrative commands for bootstrapping and maintaining the shellbrain database.

    Example:
      shellbrain admin migrate
    """
)

_MIGRATE_HELP = dedent(
    """\
    Apply packaged Alembic migrations to the database referenced by `SHELLBRAIN_DB_DSN`.

    Example:
      SHELLBRAIN_DB_DSN=postgresql+psycopg://shellbrain:shellbrain@localhost:5432/shellbrain shellbrain admin migrate
    """
)


def _load_payload(json_text: str | None, json_file: str | None) -> dict[str, Any]:
    """This function loads a payload from either inline JSON text or a JSON file."""

    if json_text:
        return json.loads(json_text)
    if json_file:
        content = Path(json_file).read_text(encoding="utf-8")
        return json.loads(content)
    raise ValueError("Either --json or --json-file is required")


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser with operator help and subcommands."""

    parser = argparse.ArgumentParser(
        prog="shellbrain",
        description="Shellbrain CLI for repo-scoped recall and evidence-backed writes.",
        epilog=_TOP_LEVEL_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(parser)
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="command")

    create_parser = subparsers.add_parser(
        "create",
        help="Create one Shellbrain entry from explicit evidence.",
        description="Create one durable Shellbrain entry from explicit evidence references.",
        epilog=_CREATE_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(create_parser, suppress_default=True)
    _add_payload_arguments(create_parser)

    read_parser = subparsers.add_parser(
        "read",
        help="Read Shellbrain context without mutating state.",
        description="Retrieve Shellbrain context relevant to one repo-scoped question.",
        epilog=_READ_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(read_parser, suppress_default=True)
    _add_payload_arguments(read_parser)

    events_parser = subparsers.add_parser(
        "events",
        help="Inspect recent host transcript events.",
        description="Return recent episode events from the newest repo-matching host session.",
        epilog=_EVENTS_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(events_parser, suppress_default=True)
    _add_payload_arguments(events_parser)

    update_parser = subparsers.add_parser(
        "update",
        help="Update one existing Shellbrain entry from explicit evidence.",
        description="Apply one evidence-backed update to an existing memory.",
        epilog=_UPDATE_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(update_parser, suppress_default=True)
    _add_payload_arguments(update_parser)

    admin_parser = subparsers.add_parser(
        "admin",
        help="Administrative bootstrap commands.",
        description="Administrative commands for database bootstrap and maintenance.",
        epilog=_ADMIN_HELP,
        formatter_class=_HelpFormatter,
    )
    admin_subparsers = admin_parser.add_subparsers(dest="admin_command", required=True, metavar="admin-command")
    admin_subparsers.add_parser(
        "migrate",
        help="Apply packaged schema migrations to the configured database.",
        description="Apply packaged Alembic migrations to the database referenced by SHELLBRAIN_DB_DSN.",
        epilog=_MIGRATE_HELP,
        formatter_class=_HelpFormatter,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and dispatch to the requested operational or admin path."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "admin":
        return _run_admin_command(args)

    try:
        repo_context = resolve_repo_context(
            repo_root_arg=getattr(args, "repo_root", None),
            repo_id_arg=getattr(args, "repo_id", None),
        )
        payload = _load_payload(getattr(args, "json_text", None), getattr(args, "json_file", None))
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    result = _dispatch_operation_command(args.command, payload, repo_context)
    _print_operation_result(result)
    if result.get("status") == "ok" and not getattr(args, "no_sync", False):
        _maybe_start_sync(repo_context)
    return 0


def _add_repo_context_arguments(parser: argparse.ArgumentParser, *, suppress_default: bool = False) -> None:
    """Add shared repo-targeting and sync-control arguments to one parser."""

    kwargs = {"default": argparse.SUPPRESS} if suppress_default else {}
    parser.add_argument(
        "--repo-root",
        help="Target repository root. Defaults to the current working directory.",
        **kwargs,
    )
    parser.add_argument(
        "--repo-id",
        help="Override the inferred repo identifier. Defaults to basename(repo_root).",
        **kwargs,
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Do not start the repo-local episode sync poller after a successful command.",
        **kwargs,
    )


def _add_payload_arguments(parser: argparse.ArgumentParser) -> None:
    """Require one JSON payload source for an operational subcommand."""

    payload_group = parser.add_mutually_exclusive_group(required=True)
    payload_group.add_argument("--json", dest="json_text", help="Inline JSON payload.")
    payload_group.add_argument("--json-file", dest="json_file", help="Path to a JSON payload file.")


def _dispatch_operation_command(command: str, payload: dict[str, Any], repo_context: RepoContext) -> dict[str, Any]:
    """Resolve runtime dependencies lazily and execute one operational command."""

    from shellbrain.boot.create_policy import get_create_hydration_defaults
    from shellbrain.boot.read_policy import get_read_hydration_defaults
    from shellbrain.boot.use_cases import get_embedding_model, get_embedding_provider_factory, get_uow_factory
    from shellbrain.periphery.cli.handlers import handle_create, handle_events, handle_read, handle_update

    uow_factory = get_uow_factory()
    if command == "create":
        return handle_create(
            payload,
            uow_factory=uow_factory,
            embedding_provider_factory=get_embedding_provider_factory(),
            embedding_model=get_embedding_model(),
            inferred_repo_id=repo_context.repo_id,
            defaults=get_create_hydration_defaults(),
        )
    if command == "read":
        return handle_read(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=repo_context.repo_id,
            defaults=get_read_hydration_defaults(),
        )
    if command == "update":
        return handle_update(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=repo_context.repo_id,
        )
    if command == "events":
        return handle_events(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=repo_context.repo_id,
            repo_root=repo_context.repo_root,
        )
    raise ValueError(f"Unsupported command: {command}")


def _run_admin_command(args: argparse.Namespace) -> int:
    """Execute one admin command."""

    if args.admin_command != "migrate":
        raise ValueError(f"Unsupported admin command: {args.admin_command}")

    from shellbrain.boot.migrations import upgrade_database

    upgrade_database()
    print("Applied shellbrain schema migrations to head.")
    return 0


def _print_operation_result(result: dict[str, Any]) -> None:
    """Render one operation result as JSON for agent consumption."""

    from shellbrain.periphery.cli.presenter_json import render

    print(render(result))


def _maybe_start_sync(repo_context: RepoContext) -> None:
    """Best-effort startup for repo-local episode sync after a successful command."""

    try:
        from shellbrain.periphery.episodes.launcher import ensure_episode_sync_started

        ensure_episode_sync_started(repo_id=repo_context.repo_id, repo_root=repo_context.repo_root)
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
