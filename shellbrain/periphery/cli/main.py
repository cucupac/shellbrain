"""This module defines the CLI entry point for shellbrain operations and admin commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Sequence
from uuid import uuid4

from shellbrain.periphery.cli.hydration import resolve_repo_context

if TYPE_CHECKING:
    from shellbrain.periphery.cli.hydration import RepoContext


class _HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Keep multiline examples readable in CLI help output."""


_TOP_LEVEL_HELP = dedent(
    """\
    Use Shellbrain as a case-based memory system for agent work.

    Mental model:
      - `read` retrieves durable memories related to the concrete problem or subproblem.
      - `events` inspects episodic transcript evidence from the active session.
      - `create` authors durable memories from that evidence.
      - `update` records utility, truth-evolution links, and explicit associations.

    Codex shell bootstrap:
      - In Codex Desktop or similar tool shells, start via `zsh -lc 'source ~/.zprofile >/dev/null 2>&1; shellbrain --help'`.
      - Use the same wrapper shape for actual Shellbrain commands when the session depends on machine-level PATH and `SHELLBRAIN_DB_DSN`.

    Typical workflow:
      1. Query with the concrete bug, subsystem, decision, or constraint you are working on.
         Avoid generic prompts like "what should I know about this repo?"
      2. Re-run `read` whenever the search shifts or you get stuck.
      3. Run `events` before every write and reuse returned ids verbatim as `evidence_refs`.
      4. At session end, normalize the episode into `problem`, `failed_tactic`, `solution`, `fact`, `preference`, and `change` memories, then record `utility_vote` updates for memories that helped or misled.

    Prerequisites:
      - Shellbrain should already be available from a one-time global install.
      - If it is missing, restore the machine-level install (`pipx install --editable /path/to/shellbrain` or `python3 -m pip install --user --break-system-packages --editable /path/to/shellbrain`).
      - Export `SHELLBRAIN_DB_DSN` from your shell profile.
      - In Codex Desktop or similar tool shells, put the PATH export and `SHELLBRAIN_DB_DSN` in `~/.zprofile`, not `~/.zshrc`.
      - Run `shellbrain admin migrate` once against the target database.

    Examples:
      shellbrain read --json '{"query":"Have we seen this migration lock timeout before?","kinds":["problem","solution","failed_tactic"]}'
      shellbrain read --json '{"query":"What repo constraints or user preferences matter for this auth refactor?","kinds":["fact","preference","change"]}'
      shellbrain events --json '{"limit":10}'
      shellbrain create --json '{"memory":{"text":"Migration failed because the lock timeout was too low","kind":"problem","evidence_refs":["evt-123"]}}'
      shellbrain update --json '{"memory_id":"mem-older-solution","update":{"type":"utility_vote","problem_id":"mem-problem-123","vote":1.0,"evidence_refs":["evt-124"]}}'
      shellbrain admin migrate

    Common recovery steps:
      - `shellbrain: command not found` inside Codex: verify you used the `zsh -lc 'source ~/.zprofile ...'` startup pattern before declaring Shellbrain blocked.
      - `SHELLBRAIN_DB_DSN is not set`: verify the same startup pattern and that the export lives in `~/.zprofile`, then export the database DSN if needed.
      - No active host session found: verify Codex/Claude Code transcript availability, then rerun `events`.
      - Evidence ref rejected: rerun `events` and use the returned `episode_event` ids verbatim.
      - Wrong working tree: rerun with `--repo-root` (and optionally `--repo-id`) for the target repo.
    """
)

_CREATE_HELP = dedent(
    """\
    Create one durable Shellbrain entry from explicit evidence.

    Choose the memory kind deliberately:
      - `problem`: the obstacle or failure mode
      - `solution`: what worked for a specific problem
      - `failed_tactic`: what did not work for a specific problem
      - `fact`: durable truth
      - `preference`: durable convention
      - `change`: truth invalidation or revision

    `solution` and `failed_tactic` require `memory.links.problem_id`.

    Example:
      shellbrain create --json '{"memory":{"text":"The staging DB migration needs a 30s lock timeout","kind":"fact","evidence_refs":["evt-123"]}}'
    """
)

_READ_HELP = dedent(
    """\
    Retrieve Shellbrain context without mutating state.

    Use concrete failure modes, subsystem names, decisions, or constraints.
    Avoid generic prompts like "what should I know about this repo?"

    Returned pack sections:
      - `direct`
      - `explicit_related`
      - `implicit_related`

    Example:
      shellbrain read --json '{"query":"Have we seen this migration lock timeout before?","kinds":["problem","solution","failed_tactic"]}'
    """
)

_EVENTS_HELP = dedent(
    """\
    Inspect the newest repo-matching host session and return recent `episode_event` ids.

    `events` performs an inline transcript sync before returning normalized episodic evidence.

    Example:
      shellbrain events --json '{"limit":10}'
    """
)

_UPDATE_HELP = dedent(
    """\
    Update one existing Shellbrain entry.

    Update types:
      - `archive_state`
      - `utility_vote` (`-1.0` to `1.0`; negative = unhelpful, `0.0` = neutral, positive = helpful)
      - `fact_update_link`
      - `association_link`

    Example:
      shellbrain update --json '{"memory_id":"mem-older-solution","update":{"type":"utility_vote","problem_id":"mem-problem-123","vote":1.0,"evidence_refs":["evt-456"]}}'
    """
)

_ADMIN_HELP = dedent(
    """\
    Administrative commands for bootstrapping and maintaining the shellbrain database.

    Example:
      shellbrain admin migrate
    """
)

_INSTALL_CLAUDE_HOOK_HELP = dedent(
    """\
    Install or update the repo-local Claude Code SessionStart hook used for trusted Shellbrain caller identity.

    Example:
      shellbrain admin install-claude-hook --repo-root /path/to/repo
    """
)

_SESSION_STATE_HELP = dedent(
    """\
    Inspect or clean repo-local per-caller Shellbrain session state.

    Examples:
      shellbrain admin session-state inspect --caller-id codex:thread-123
      shellbrain admin session-state clear --caller-id codex:thread-123
      shellbrain admin session-state gc
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
    install_hook_parser = admin_subparsers.add_parser(
        "install-claude-hook",
        help="Install the repo-local Claude hook used for trusted caller identity.",
        description="Install or update the repo-local Claude Code SessionStart hook used by Shellbrain.",
        epilog=_INSTALL_CLAUDE_HOOK_HELP,
        formatter_class=_HelpFormatter,
    )
    install_hook_parser.add_argument("--repo-root", help="Target repository root. Defaults to the current working directory.")

    session_state_parser = admin_subparsers.add_parser(
        "session-state",
        help="Inspect or clean repo-local per-caller Shellbrain session state.",
        description="Inspect or clean repo-local per-caller Shellbrain session state.",
        epilog=_SESSION_STATE_HELP,
        formatter_class=_HelpFormatter,
    )
    session_state_parser.add_argument("--repo-root", help="Target repository root. Defaults to the current working directory.")
    session_state_subparsers = session_state_parser.add_subparsers(
        dest="session_state_command",
        required=True,
        metavar="session-state-command",
    )
    inspect_parser = session_state_subparsers.add_parser("inspect", help="Print one caller state as JSON.")
    inspect_parser.add_argument("--caller-id", required=True)
    clear_parser = session_state_subparsers.add_parser("clear", help="Delete one caller state.")
    clear_parser.add_argument("--caller-id", required=True)
    session_state_subparsers.add_parser("gc", help="Delete stale caller state files.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments and dispatch to the requested operational or admin path."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "admin":
        return _run_admin_command(args)

    try:
        from shellbrain.core.entities.runtime_context import RuntimeContext
        from shellbrain.periphery.identity.resolver import resolve_caller_identity
        from shellbrain.periphery.telemetry import reset_operation_telemetry_context, set_operation_telemetry_context

        repo_context = resolve_repo_context(
            repo_root_arg=getattr(args, "repo_root", None),
            repo_id_arg=getattr(args, "repo_id", None),
        )
        payload = _load_payload(getattr(args, "json_text", None), getattr(args, "json_file", None))
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    caller_identity_resolution = resolve_caller_identity()
    operation_context = RuntimeContext(
        invocation_id=str(uuid4()),
        repo_root=str(repo_context.repo_root),
        no_sync=bool(getattr(args, "no_sync", False)),
        caller_identity=caller_identity_resolution.caller_identity,
        caller_identity_error=caller_identity_resolution.error,
    )
    token = set_operation_telemetry_context(operation_context)
    try:
        result = _dispatch_operation_command(args.command, payload, repo_context)
        _print_operation_result(result)
        if result.get("status") == "ok":
            if getattr(args, "no_sync", False):
                _update_operation_polling_status(
                    invocation_id=operation_context.invocation_id,
                    attempted=False,
                    started=False,
                )
            else:
                started = bool(_maybe_start_sync(repo_context))
                _update_operation_polling_status(
                    invocation_id=operation_context.invocation_id,
                    attempted=True,
                    started=started,
                )
        return 0
    finally:
        reset_operation_telemetry_context(token)


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
        help=argparse.SUPPRESS,
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
    from shellbrain.periphery.telemetry import get_operation_telemetry_context

    uow_factory = get_uow_factory()
    if command == "create":
        return handle_create(
            payload,
            uow_factory=uow_factory,
            embedding_provider_factory=get_embedding_provider_factory(),
            embedding_model=get_embedding_model(),
            inferred_repo_id=repo_context.repo_id,
            defaults=get_create_hydration_defaults(),
            telemetry_context=get_operation_telemetry_context(),
            repo_root=repo_context.repo_root,
        )
    if command == "read":
        return handle_read(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=repo_context.repo_id,
            defaults=get_read_hydration_defaults(),
            telemetry_context=get_operation_telemetry_context(),
            repo_root=repo_context.repo_root,
        )
    if command == "update":
        return handle_update(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=repo_context.repo_id,
            telemetry_context=get_operation_telemetry_context(),
            repo_root=repo_context.repo_root,
        )
    if command == "events":
        return handle_events(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=repo_context.repo_id,
            repo_root=repo_context.repo_root,
            telemetry_context=get_operation_telemetry_context(),
        )
    raise ValueError(f"Unsupported command: {command}")


def _run_admin_command(args: argparse.Namespace) -> int:
    """Execute one admin command."""

    if args.admin_command == "migrate":
        from shellbrain.boot.migrations import upgrade_database

        upgrade_database()
        print("Applied shellbrain schema migrations to head.")
        return 0

    repo_root = _resolve_admin_repo_root(getattr(args, "repo_root", None))
    if args.admin_command == "install-claude-hook":
        from shellbrain.periphery.identity.claude_hook_install import install_claude_hook

        settings_path = install_claude_hook(repo_root=repo_root)
        print(f"Installed Claude hook at {settings_path}")
        return 0

    if args.admin_command == "session-state":
        from shellbrain.periphery.session_state.file_store import FileSessionStateStore

        store = FileSessionStateStore()
        subcommand = getattr(args, "session_state_command", None)
        if subcommand == "inspect":
            state = store.load(repo_root=repo_root, caller_id=args.caller_id)
            print(json.dumps(None if state is None else state.__dict__, indent=2, sort_keys=True))
            return 0
        if subcommand == "clear":
            store.delete(repo_root=repo_root, caller_id=args.caller_id)
            print(f"Cleared session state for {args.caller_id}")
            return 0
        if subcommand == "gc":
            from datetime import datetime, timedelta, timezone

            deleted = store.gc(
                repo_root=repo_root,
                older_than_iso=(datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
            )
            print(json.dumps({"deleted": deleted}, indent=2, sort_keys=True))
            return 0
    raise ValueError(f"Unsupported admin command: {args.admin_command}")


def _print_operation_result(result: dict[str, Any]) -> None:
    """Render one operation result as JSON for agent consumption."""

    from shellbrain.periphery.cli.presenter_json import render

    print(render(result))


def _maybe_start_sync(repo_context: RepoContext) -> bool:
    """Best-effort startup for repo-local episode sync after a successful command."""

    try:
        from shellbrain.periphery.episodes.launcher import ensure_episode_sync_started

        return bool(ensure_episode_sync_started(repo_id=repo_context.repo_id, repo_root=repo_context.repo_root))
    except Exception:
        return False


def _update_operation_polling_status(*, invocation_id: str, attempted: bool, started: bool) -> None:
    """Patch poller-start telemetry flags without affecting the visible command result."""

    try:
        from shellbrain.boot.use_cases import get_uow_factory

        with get_uow_factory()() as uow:
            uow.telemetry.update_operation_polling(
                invocation_id,
                attempted=attempted,
                started=started,
            )
    except Exception:
        return


def _resolve_admin_repo_root(repo_root_arg: str | None) -> Path:
    """Resolve one admin repo root without inferring repo_id."""

    repo_root = Path(repo_root_arg).expanduser().resolve() if repo_root_arg else Path.cwd().resolve()
    if not repo_root.exists():
        raise ValueError(f"repo_root does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise ValueError(f"repo_root must be a directory: {repo_root}")
    return repo_root


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
