"""This module defines the CLI entry point for shellbrain operations and admin commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from textwrap import dedent
from typing import TYPE_CHECKING, Any, Sequence
from uuid import uuid4

from app.periphery.cli.hydration import resolve_repo_context

if TYPE_CHECKING:
    from app.periphery.cli.hydration import RepoContext


class _HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Keep multiline examples readable in CLI help output."""


_TOP_LEVEL_HELP = dedent(
    """\
    Use Shellbrain as a case-based memory system for agent work.

    Install and bootstrap:
      1. `curl -L shellbrain.ai/install | bash`
      2. Upgrade later with `shellbrain upgrade` or `curl -L shellbrain.ai/upgrade | bash`
      3. Manual/advanced upgrade path: `pipx upgrade shellbrain && shellbrain init`
      4. The installer/upgrade flow runs `shellbrain init` for machine bootstrap and repair.
      5. Repos auto-register on first Shellbrain use inside a git repo.

    After install:
      - Start a repo session in Codex or Claude Code (see shellbrain.ai/humans).
      - If readiness is unclear, run `shellbrain admin doctor`.

    Mental model:
      - `read` retrieves durable memories related to the concrete problem or subproblem.
      - `events` inspects episodic transcript evidence from the active session.
      - `create` authors durable memories from that evidence.
      - `update` records utility, truth-evolution links, and explicit associations.

    Typical workflow:
      0. `shellbrain init` is the one-time machine bootstrap and repair command. The website installer already runs it for you.
      1. Query with the concrete bug, subsystem, decision, or constraint you are working on.
         Avoid generic prompts like "what should I know about this repo?"
      2. Re-run `read` whenever the search shifts or you get stuck.
      3. Run `events` before every write and reuse returned ids verbatim as `evidence_refs`.
      4. At session end, normalize the episode into `problem`, `failed_tactic`, `solution`, `fact`, `preference`, and `change` memories, then record `utility_vote` updates for memories that helped or misled.

    Examples:
      shellbrain init
      shellbrain upgrade
      shellbrain read --json '{"query":"Have we seen this migration lock timeout before?","kinds":["problem","solution","failed_tactic"]}'
      shellbrain read --json '{"query":"What repo constraints or user preferences matter for this auth refactor?","kinds":["fact","preference","change"]}'
      shellbrain events --json '{"limit":10}'
      shellbrain create --json '{"memory":{"text":"Migration failed because the lock timeout was too low","kind":"problem","evidence_refs":["evt-123"]}}'
      shellbrain update --json '{"memory_id":"mem-older-solution","update":{"type":"utility_vote","problem_id":"mem-problem-123","vote":1.0,"evidence_refs":["evt-124"]}}'
      shellbrain admin migrate
      shellbrain admin backup create
      shellbrain admin doctor

    Docs:
      https://shellbrain.ai/agents — how agents use shellbrain
      https://shellbrain.ai/humans — install, upgrade, and getting started

    Common recovery steps:
      - `shellbrain: command not found`: rerun `curl -L shellbrain.ai/install | bash`.
      - `Shellbrain machine config is unreadable`: rerun `shellbrain init` to repair the managed instance.
      - `Outcome: blocked_dependency`: install Docker or start the Docker daemon, then rerun `shellbrain init`.
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
      shellbrain init
      shellbrain admin migrate
    """
)

_UPGRADE_HELP = dedent(
    """\
    Upgrade the installed Shellbrain package through the hosted upgrade script.

    This is the official product-path upgrader for website installs.
    It upgrades the package and reruns `shellbrain init` to refresh the managed runtime,
    Codex skill, Claude skill, and Claude hook.

    Manual/advanced path:
      pipx upgrade shellbrain && shellbrain init

    Examples:
      shellbrain upgrade
      curl -L shellbrain.ai/upgrade | bash
    """
)

_INIT_HELP = dedent(
    """\
    Bootstrap or repair the machine-local Shellbrain runtime.

    Happy path:
      - `shellbrain init`
      - Shellbrain provisions or reuses one managed local Postgres instance, prepares embeddings, installs host integrations, and registers a repo only when one is obvious.

    Advanced:
      - `--repo-root` targets a different repo root.
      - `--repo-id` overrides repo identity when multiple remotes exist or a weak local identity is not acceptable.

    Examples:
      shellbrain init
      shellbrain init --repo-root /path/to/repo
      shellbrain init --no-host-assets
      shellbrain init --skip-model-download
    """
)

_BACKUP_HELP = dedent(
    """\
    Create, list, verify, and restore Shellbrain logical backups.

    Examples:
      shellbrain admin backup create
      shellbrain admin backup list
      shellbrain admin backup verify
      shellbrain admin backup restore --target-db shellbrain_restore_001
    """
)

_DOCTOR_HELP = dedent(
    """\
    Print one safety report for the current Shellbrain database configuration.

    Example:
      shellbrain admin doctor
    """
)

_INSTALL_CLAUDE_HOOK_HELP = dedent(
    """\
    Install or update the repo-local Claude Code SessionStart hook used as an explicit repo-local override.

    Example:
      shellbrain admin install-claude-hook --repo-root /path/to/repo
    """
)

_INSTALL_HOST_ASSETS_HELP = dedent(
    """\
    Install or update Shellbrain-managed Codex and Claude host integrations.

    Examples:
      shellbrain admin install-host-assets --host auto
      shellbrain admin install-host-assets --host codex
      shellbrain admin install-host-assets --host claude --force
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
    Apply packaged Alembic migrations to the database referenced by `SHELLBRAIN_DB_ADMIN_DSN`.

    Example:
      SHELLBRAIN_DB_ADMIN_DSN=postgresql+psycopg://shellbrain_admin:shellbrain_admin@localhost:5432/shellbrain shellbrain admin migrate
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

    init_parser = subparsers.add_parser(
        "init",
        help="Bootstrap or repair the managed Shellbrain runtime.",
        description="Bootstrap or repair the machine-local Shellbrain runtime and default host integrations.",
        epilog=_INIT_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(init_parser, suppress_default=True)
    init_parser.add_argument(
        "--skip-model-download",
        action="store_true",
        help="Skip embedding model prewarm during init.",
    )
    init_parser.add_argument(
        "--no-host-assets",
        action="store_true",
        help="Skip Codex skill, Claude skill, and Claude global hook installation during init.",
    )

    subparsers.add_parser(
        "upgrade",
        help="Upgrade Shellbrain and rerun init through the hosted upgrader.",
        description="Upgrade Shellbrain through the hosted upgrade script and rerun init.",
        epilog=_UPGRADE_HELP,
        formatter_class=_HelpFormatter,
    )

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
        description="Apply packaged Alembic migrations to the database referenced by SHELLBRAIN_DB_ADMIN_DSN.",
        epilog=_MIGRATE_HELP,
        formatter_class=_HelpFormatter,
    )
    backup_parser = admin_subparsers.add_parser(
        "backup",
        help="Create, list, verify, and restore Shellbrain logical backups.",
        description="Create, list, verify, and restore Shellbrain logical backups.",
        epilog=_BACKUP_HELP,
        formatter_class=_HelpFormatter,
    )
    backup_subparsers = backup_parser.add_subparsers(dest="backup_command", required=True, metavar="backup-command")
    backup_subparsers.add_parser("create", help="Create one logical backup for the configured database.")
    backup_subparsers.add_parser("list", help="List available backup manifests.")
    verify_parser = backup_subparsers.add_parser("verify", help="Verify one backup artifact, defaulting to the newest.")
    verify_parser.add_argument("--backup-id", help="Optional backup id to verify. Defaults to the newest backup.")
    restore_parser = backup_subparsers.add_parser("restore", help="Restore one backup into a fresh scratch database.")
    restore_parser.add_argument("--target-db", required=True, help="Name of the scratch restore database to create.")
    restore_parser.add_argument("--backup-id", help="Optional backup id to restore. Defaults to the newest backup.")
    admin_subparsers.add_parser(
        "doctor",
        help="Print one Shellbrain safety report for DB role, instance mode, and backups.",
        description="Print one Shellbrain safety report for DB role, instance mode, and backups.",
        epilog=_DOCTOR_HELP,
        formatter_class=_HelpFormatter,
    )
    admin_subparsers.choices["doctor"].add_argument(
        "--repo-root",
        help="Optional repo root for repo registration and Claude integration diagnostics.",
    )
    install_hook_parser = admin_subparsers.add_parser(
        "install-claude-hook",
        help="Install the repo-local Claude hook used for trusted caller identity.",
        description="Install or update the repo-local Claude Code SessionStart hook used by Shellbrain.",
        epilog=_INSTALL_CLAUDE_HOOK_HELP,
        formatter_class=_HelpFormatter,
    )
    install_hook_parser.add_argument("--repo-root", help="Target repository root. Defaults to the current working directory.")
    install_host_assets_parser = admin_subparsers.add_parser(
        "install-host-assets",
        help="Install Shellbrain-managed Codex and Claude host integrations.",
        description="Install or update Shellbrain-managed Codex and Claude host integrations.",
        epilog=_INSTALL_HOST_ASSETS_HELP,
        formatter_class=_HelpFormatter,
    )
    install_host_assets_parser.add_argument(
        "--host",
        choices=("auto", "codex", "claude", "all"),
        default="auto",
        help="Host asset install mode. Defaults to auto.",
    )
    install_host_assets_parser.add_argument(
        "--force",
        action="store_true",
        help="Replace conflicting unmanaged installs.",
    )

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

    if args.command == "init":
        try:
            from app.periphery.admin.init import run_init

            repo_root = _resolve_admin_repo_root(getattr(args, "repo_root", None))
        except ValueError as exc:
            parser.error(str(exc))
            return 2
        result = run_init(
            repo_root=repo_root,
            repo_id_override=getattr(args, "repo_id", None),
            register_repo_now=_should_register_repo_during_init(
                repo_root=repo_root,
                repo_root_arg=getattr(args, "repo_root", None),
                repo_id_arg=getattr(args, "repo_id", None),
            ),
            skip_model_download=bool(getattr(args, "skip_model_download", False)),
            skip_host_assets=bool(getattr(args, "no_host_assets", False)),
        )
        print(f"Outcome: {result.outcome}")
        for line in result.lines:
            print(line)
        return result.exit_code

    if args.command == "upgrade":
        from app.periphery.admin.upgrade import run_upgrade

        return run_upgrade()

    if args.command == "admin":
        return _run_admin_command(args)

    try:
        from app.core.entities.runtime_context import RuntimeContext
        from app.periphery.identity.resolver import resolve_caller_identity
        from app.periphery.telemetry import reset_operation_telemetry_context, set_operation_telemetry_context

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
        try:
            _warn_or_fail_on_unsafe_app_role()
            _ensure_repo_registration_for_operation(
                repo_context=repo_context,
                repo_id_override=getattr(args, "repo_id", None),
            )
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
        except (RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
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
        help="Override the inferred repo identifier. Advanced: use when multiple remotes exist or you need a durable local override.",
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

    from app.boot.create_policy import get_create_hydration_defaults
    from app.boot.read_policy import get_read_hydration_defaults
    from app.boot.use_cases import get_embedding_model, get_embedding_provider_factory, get_uow_factory
    from app.periphery.cli.handlers import handle_create, handle_events, handle_read, handle_update
    from app.periphery.telemetry import get_operation_telemetry_context

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
        from app.boot.migrations import upgrade_database

        upgrade_database()
        print("Applied shellbrain schema migrations to head.")
        return 0

    if args.admin_command == "backup":
        from app.boot.db import get_optional_db_dsn
        from app.boot.admin_db import get_admin_db_dsn, get_backup_dir, get_backup_mirror_dir
        from app.periphery.admin.backup import create_backup, list_backups, verify_backup
        from app.periphery.admin.machine_state import try_load_machine_config
        from app.periphery.admin.restore import restore_backup

        admin_dsn = get_admin_db_dsn()
        backup_root = get_backup_dir()
        mirror_root = get_backup_mirror_dir()
        managed_backup_kwargs = _managed_backup_kwargs(*try_load_machine_config())
        subcommand = getattr(args, "backup_command", None)
        if subcommand == "create":
            manifest = create_backup(
                admin_dsn=admin_dsn,
                backup_root=backup_root,
                mirror_root=mirror_root,
                **managed_backup_kwargs,
            )
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
                **_managed_restore_kwargs(managed_backup_kwargs),
            )
            print(json.dumps({"restored_backup_id": manifest.backup_id, "target_db": args.target_db}, indent=2, sort_keys=True))
            return 0

    if args.admin_command == "doctor":
        from app.boot.admin_db import get_backup_dir, get_optional_admin_db_dsn
        from app.boot.db import get_optional_db_dsn
        from app.periphery.admin.doctor import build_doctor_report

        report = build_doctor_report(
            app_dsn=get_optional_db_dsn(),
            admin_dsn=get_optional_admin_db_dsn(),
            backup_root=get_backup_dir(),
            repo_root=_resolve_admin_repo_root(getattr(args, "repo_root", None)),
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    repo_root = _resolve_admin_repo_root(getattr(args, "repo_root", None))
    if args.admin_command == "install-claude-hook":
        from app.periphery.identity.claude_hook_install import install_claude_hook

        settings_path = install_claude_hook(repo_root=repo_root)
        print(f"Installed Claude hook at {settings_path}")
        return 0
    if args.admin_command == "install-host-assets":
        from app.periphery.onboarding.host_assets import install_host_assets

        result = install_host_assets(host_mode=args.host, force=bool(args.force))
        for line in result.lines:
            print(line)
        return 0

    if args.admin_command == "session-state":
        from app.periphery.session_state.file_store import FileSessionStateStore

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

    from app.periphery.cli.presenter_json import render

    print(render(result))


def _maybe_start_sync(repo_context: RepoContext) -> bool:
    """Best-effort startup for repo-local episode sync after a successful command."""

    try:
        from app.periphery.episodes.launcher import ensure_episode_sync_started

        return bool(ensure_episode_sync_started(repo_id=repo_context.repo_id, repo_root=repo_context.repo_root))
    except Exception:
        return False


def _update_operation_polling_status(*, invocation_id: str, attempted: bool, started: bool) -> None:
    """Patch poller-start telemetry flags without affecting the visible command result."""

    try:
        from app.boot.use_cases import get_uow_factory

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


def _should_register_repo_during_init(*, repo_root: Path, repo_root_arg: str | None, repo_id_arg: str | None) -> bool:
    """Return whether init should register one repo immediately."""

    from app.periphery.admin.repo_state import load_repo_registration_for_target, resolve_git_root

    if repo_root_arg is not None or repo_id_arg is not None:
        return True
    if resolve_git_root(repo_root) is not None:
        return True
    return load_repo_registration_for_target(repo_root) is not None


def _ensure_repo_registration_for_operation(*, repo_context: RepoContext, repo_id_override: str | None) -> None:
    """Best-effort auto-registration of one repo before a real Shellbrain operation."""

    if repo_context.registration_root is None:
        return
    try:
        from app.periphery.admin.machine_state import try_load_machine_config
        from app.periphery.admin.repo_state import register_repo_for_target

        machine_config, machine_error = try_load_machine_config()
        if machine_error is not None or machine_config is None:
            return
        register_repo_for_target(
            repo_root=repo_context.registration_root,
            machine_instance_id=machine_config.machine_instance_id,
            explicit_repo_id=repo_id_override,
        )
    except Exception:
        return


def _managed_backup_kwargs(machine_config, machine_error: str | None) -> dict[str, Any]:
    """Return managed-container backup kwargs when machine config is active and readable."""

    if machine_error is not None or machine_config is None or machine_config.runtime_mode != "managed_local":
        return {}
    return {
        "container_name": machine_config.managed.container_name,
        "container_db_name": machine_config.managed.db_name,
        "container_admin_user": machine_config.managed.admin_user,
        "container_admin_password": machine_config.managed.admin_password,
    }


def _managed_restore_kwargs(managed_backup_kwargs: dict[str, Any]) -> dict[str, Any]:
    """Trim backup kwargs down to the subset restore understands."""

    return {
        key: value
        for key, value in managed_backup_kwargs.items()
        if key in {"container_name", "container_admin_user", "container_admin_password"}
    }


def _warn_or_fail_on_unsafe_app_role() -> None:
    """Emit one warning, or fail in strict mode, when the app DSN is overprivileged."""

    from app.boot.admin_db import should_fail_on_unsafe_app_role
    from app.boot.db import get_db_dsn
    from app.periphery.admin.instance_guard import SCRATCH, TEST, fetch_instance_metadata, inspect_role_safety

    dsn = get_db_dsn()
    warnings = inspect_role_safety(dsn)
    if not warnings:
        return
    message = "Unsafe Shellbrain app-role configuration:\n- " + "\n- ".join(warnings)
    metadata = fetch_instance_metadata(dsn)
    if metadata is not None and metadata.instance_mode in {TEST, SCRATCH}:
        print(message, file=sys.stderr)
        return
    if should_fail_on_unsafe_app_role():
        raise ValueError(message)
    print(message, file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
