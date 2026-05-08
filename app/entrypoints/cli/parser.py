"""Argument parser construction for the Shellbrain CLI."""

from __future__ import annotations

import argparse
import importlib.metadata
from textwrap import dedent


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

    Managed-local prerequisites:
      - macOS or Linux
      - Python 3.11+ required
      - Docker installed and daemon running
      - First init downloads a local embedding model and boots PostgreSQL + pgvector inside a managed Docker container.
      - Windows and first-class external Postgres adoption are not part of this happy path.

    After install:
      - Start a repo session in Codex, Claude Code, or Cursor (see shellbrain.ai/humans).
      - If readiness is unclear, run `shellbrain admin doctor`.

    Mental model:
      - `read` retrieves durable memories related to the concrete problem or subproblem.
      - `recall` returns a compact read-only brief from targeted Shellbrain retrieval.
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
      shellbrain metrics
      shellbrain read --json '{"query":"Have we seen this migration lock timeout before?","kinds":["problem","solution","failed_tactic"]}'
      shellbrain recall --json '{"query":"What context matters for this migration lock timeout?"}'
      shellbrain read --json '{"query":"What repo constraints or user preferences matter for this auth refactor?","kinds":["fact","preference","change"]}'
      shellbrain events --json '{"limit":10}'
      shellbrain create --json '{"memory":{"text":"Migration failed because the lock timeout was too low","kind":"problem","evidence_refs":["evt-123"]}}'
      shellbrain update --json '{"memory_id":"mem-older-solution","update":{"type":"utility_vote","problem_id":"mem-problem-123","vote":1.0,"evidence_refs":["evt-124"]}}'
      shellbrain admin migrate
      shellbrain admin backup create
      shellbrain admin doctor
      shellbrain admin analytics --days 2

    Docs:
      https://shellbrain.ai/agents — how agents use shellbrain
      https://shellbrain.ai/humans — install, upgrade, and getting started

    Common recovery steps:
      - `shellbrain: command not found`: rerun `curl -L shellbrain.ai/install | bash`.
      - `Shellbrain machine config is unreadable`: rerun `shellbrain init` to repair the managed instance.
      - `Outcome: blocked_dependency`: install Docker or start the Docker daemon, then rerun `shellbrain init`.
      - No active host session found: verify Codex, Claude Code, or Cursor transcript availability, then rerun `events`.
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
      - `concepts`

    Example:
      shellbrain read --json '{"query":"Have we seen this migration lock timeout before?","kinds":["problem","solution","failed_tactic"]}'
      shellbrain read --json '{"query":"debug deposit address refund failure","expand":{"concepts":{"mode":"explicit","refs":["deposit-addresses"],"facets":["groundings"]}}}'
    """
)

_RECALL_HELP = dedent(
    """\
    Return a compact read-only recall brief.

    Phase 1 accepts only `query` and optional `limit`.
    It does not mutate memories, concepts, utility observations, or problem runs.

    Example:
      shellbrain recall --json '{"query":"What context matters for this migration lock timeout?"}'
    """
)

_CONCEPT_HELP = dedent(
    """\
    Internal JSON-first endpoint for Shellbrain concept graph substrate operations.

    This endpoint is intended for tests, manual seeding, and future librarian integration.
    Normal worker agents should continue using `read`, `events`, `create`, and `update`.

    Phase 1 supports:
      - mode: apply
      - mode: show

    Examples:
      shellbrain concept --json '{"schema_version":"concept.v1","mode":"apply","actions":[{"type":"upsert_concept","slug":"deposit-addresses","name":"Deposit Addresses","kind":"domain"}]}'
      shellbrain concept --json '{"schema_version":"concept.v1","mode":"show","concept":"deposit-addresses","include":["claims","preview_concept"]}'
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
    Codex skill, Claude skill, Cursor skill, and Claude hook.

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
      - On first bootstrap, Shellbrain asks how it should store data.
      - The recommended default provisions or reuses one managed local PostgreSQL + pgvector instance, prepares embeddings, installs host integrations, and registers a repo only when one is obvious.
      - External mode uses an existing PostgreSQL database with pgvector.
      - Requirements for managed-local mode: macOS or Linux, Python 3.11+, and Docker installed with the daemon running.

    Advanced:
      - `--repo-root` targets a different repo root.
      - `--repo-id` overrides repo identity when multiple remotes exist or a weak local identity is not acceptable.
      - `--storage managed|external` skips the first-run storage prompt.
      - External mode requires `--admin-dsn` in non-interactive runs.

    Examples:
      shellbrain init
      shellbrain init --repo-root /path/to/repo
      shellbrain init --no-host-assets
      shellbrain init --skip-model-download
      shellbrain init --storage external --admin-dsn postgresql+psycopg://admin:password@host:5432/shellbrain
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

_ANALYTICS_HELP = dedent(
    """\
    Print one cross-repo usage analytics report for reviewer agents.

    Example:
      shellbrain admin analytics --days 2
    """
)

_BACKFILL_TOKEN_USAGE_HELP = dedent(
    """\
    Backfill normalized model-token telemetry from Shellbrain-linked host session files.

    Example:
      shellbrain admin backfill-token-usage
    """
)

_METRICS_HELP = dedent(
    """\
    Generate lightweight metrics snapshots, write local artifacts, and open one browser dashboard that switches repos with arrow keys.

    Example:
      shellbrain metrics
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
    Install or update Shellbrain-managed Codex, Claude, and Cursor host integrations.

    Examples:
      shellbrain admin install-host-assets --host auto
      shellbrain admin install-host-assets --host codex
      shellbrain admin install-host-assets --host cursor
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
      SHELLBRAIN_DB_ADMIN_DSN=postgresql+psycopg://<admin-user>:<admin-password>@localhost:5432/<database-name> shellbrain admin migrate
    """
)


def _installed_shellbrain_version() -> str:
    """Return the installed Shellbrain package version, falling back in editable dev mode."""

    try:
        return importlib.metadata.version("shellbrain")
    except importlib.metadata.PackageNotFoundError:
        return "dev"


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser with operator help and subcommands."""

    parser = argparse.ArgumentParser(
        prog="shellbrain",
        description="Shellbrain CLI for repo-scoped recall and evidence-backed writes.",
        epilog=_TOP_LEVEL_HELP,
        formatter_class=_HelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_installed_shellbrain_version()}",
    )
    _add_repo_context_arguments(parser)
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="command")

    init_parser = subparsers.add_parser(
        "init",
        help="Bootstrap or repair the Shellbrain runtime.",
        description="Bootstrap or repair the Shellbrain runtime and default host integrations.",
        epilog=_INIT_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(init_parser, suppress_default=True)
    init_parser.add_argument(
        "--storage",
        choices=("managed", "external"),
        help="Choose managed local PostgreSQL + pgvector or an existing external PostgreSQL + pgvector database.",
    )
    init_parser.add_argument(
        "--admin-dsn",
        help="Admin PostgreSQL DSN for external storage mode. Required for non-interactive external init.",
    )
    init_parser.add_argument(
        "--skip-model-download",
        action="store_true",
        help="Skip embedding model prewarm during init.",
    )
    init_parser.add_argument(
        "--no-host-assets",
        action="store_true",
        help="Skip Codex skill, Claude skill, Cursor skill, and Claude global hook installation during init.",
    )

    subparsers.add_parser(
        "upgrade",
        help="Upgrade Shellbrain and rerun init through the hosted upgrader.",
        description="Upgrade Shellbrain through the hosted upgrade script and rerun init.",
        epilog=_UPGRADE_HELP,
        formatter_class=_HelpFormatter,
    )

    subparsers.add_parser(
        "metrics",
        help="Browse Shellbrain metrics across repos.",
        description="Generate local metrics snapshots and open one browser dashboard for all repos.",
        epilog=_METRICS_HELP,
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

    recall_parser = subparsers.add_parser(
        "recall",
        help="Return a compact read-only Shellbrain brief.",
        description="Return a compact deterministic brief from targeted Shellbrain retrieval.",
        epilog=_RECALL_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(recall_parser, suppress_default=True)
    _add_payload_arguments(recall_parser)

    concept_parser = subparsers.add_parser(
        "concept",
        help="Internal JSON-first concept graph endpoint.",
        description="Apply or inspect typed concept graph substrate records.",
        epilog=_CONCEPT_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(concept_parser, suppress_default=True)
    _add_payload_arguments(concept_parser)

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
    analytics_parser = admin_subparsers.add_parser(
        "analytics",
        help="Print one cross-repo usage analytics report for reviewer agents.",
        description="Print one cross-repo usage analytics report for reviewer agents.",
        epilog=_ANALYTICS_HELP,
        formatter_class=_HelpFormatter,
    )
    analytics_parser.add_argument(
        "--days",
        type=int,
        default=2,
        help="Number of trailing days to include in the report. Defaults to 2.",
    )
    admin_subparsers.add_parser(
        "backfill-token-usage",
        help="Backfill normalized token usage from linked host session files.",
        description="Backfill normalized token usage from Shellbrain-linked host session files.",
        epilog=_BACKFILL_TOKEN_USAGE_HELP,
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
    install_host_assets_parser = admin_subparsers.add_parser(
        "install-host-assets",
        help="Install Shellbrain-managed Codex, Claude, and Cursor host integrations.",
        description="Install or update Shellbrain-managed Codex, Claude, and Cursor host integrations.",
        epilog=_INSTALL_HOST_ASSETS_HELP,
        formatter_class=_HelpFormatter,
    )
    install_host_assets_parser.add_argument(
        "--host",
        choices=("auto", "codex", "claude", "cursor", "all"),
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

