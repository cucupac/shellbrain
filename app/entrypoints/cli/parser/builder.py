"""Argument parser construction for the Shellbrain CLI."""

from __future__ import annotations

import argparse
import importlib.metadata
from textwrap import dedent
from typing import get_args

from app.core.entities.recall_provider import RecallProvider


class _HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Keep multiline examples readable in CLI help output."""


_TOP_LEVEL_HELP = "Install: curl -L shellbrain.ai/install | bash\nUpgrade: shellbrain upgrade\nUse recall for context and snapshot after code changes.\nInternal commands: read, events, concept, memory, scenario."

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
    Shellbrain creates canonical `structural_memory_relations` as a side effect
    for those links.

    Examples:
      shellbrain memory add --json '{"memory":{"text":"Migration deadlocked because lock_timeout was unset","kind":"problem","evidence_refs":["evt-123"]}}'
      shellbrain memory add --json '{"memory":{"text":"Set lock_timeout before the migration transaction","kind":"solution","links":{"problem_id":"mem-problem-1"},"evidence_refs":["evt-124"]}}'
      shellbrain memory add --json '{"memory":{"text":"Retrying without changing lock_timeout failed again","kind":"failed_tactic","links":{"problem_id":"mem-problem-1"},"evidence_refs":["evt-125"]}}'
      shellbrain memory add --json '{"memory":{"text":"The staging DB migration needs a 30s lock timeout","kind":"fact","evidence_refs":["evt-126"]}}'
      shellbrain memory add --json '{"memory":{"text":"Prefer narrow architecture changes with guardrail tests","kind":"preference","evidence_refs":["evt-127"]}}'
      shellbrain memory add --json '{"memory":{"text":"Memory add contracts now require current problem evidence","kind":"change","evidence_refs":["evt-128"]}}'
    """
)

_READ_HELP = dedent(
    """\
    Internal knowledge-builder endpoint for raw retrieval without mutating state.

    Use concrete failure modes, subsystem names, decisions, or constraints.
    Knowledge builders use this to find existing memories and concept summaries.
    Use `concept show` for details and evidence. Working agents should call `recall`.
    Avoid generic prompts like "what should I know about this repo?"

    Returned pack sections:
      - `direct`
      - `explicit_related`
      - `implicit_related`
      - `concepts`

    Example:
      shellbrain read --json '{"query":"Have we seen this migration lock timeout before?","kinds":["problem","solution","failed_tactic"]}'
      shellbrain concept show --json '{"schema_version":"concept.v1","concept":"deposit-addresses","include":["groundings","evidence"]}'
    """
)

_RECALL_HELP = dedent(
    """\
    Return a compact read-only recall brief.

    This is the normal working-agent interface. Working agents should call
    `recall`, not internal commands like `read`, `events`, or `concept show`.

    Pass one self-contained natural-language query naming the failure mode,
    subsystem, decision, file area, or constraint that matters. Recall receives
    only this query, so include relevant task context naturally.
    It does not mutate memories, concepts, utility observations, or problem runs.

    Example:
      shellbrain recall "What context matters for this migration lock timeout?"
    """
)


_CONCEPT_HELP = dedent(
    """\
    Internal JSON-first endpoint for Shellbrain concept graph substrate operations.

    This endpoint is intended for internal knowledge-builder concept graph work.
    Working agents should use `recall`. Internal agents may use `read`, `events`,
    `concept show`, `memory add`, `memory update`, `concept add`, and `concept update`.

    Concept endpoints support:
      - concept add: create concept containers; fails when the concept exists
      - concept update: change existing concept records and graph links
      - concept show: inspect one concept and requested facets without mutating state

    Examples:
      shellbrain concept show --json '{"schema_version":"concept.v1","concept":"deposit-addresses","include":["claims","groundings","evidence","lifecycle_events"]}'
      shellbrain concept add --json '{"schema_version":"concept.v1","actions":[{"type":"add_concept","slug":"deposit-addresses","name":"Deposit Addresses","kind":"domain"}]}'
      shellbrain concept update --json '{"schema_version":"concept.v1","actions":[{"type":"add_claim","concept":"deposit-addresses","claim_type":"definition","text":"Relay-controlled EOAs users send funds to.","evidence":[{"kind":"manual","note":"Seeded from planning."}]}]}'
      shellbrain concept update --json '{"schema_version":"concept.v1","actions":[{"type":"update_lifecycle","target_type":"claim","target_id":"claim-123","status":"wrong","rationale":"Contradicted by later implementation evidence.","actor":"manual","evidence":[{"kind":"manual","note":"Verified during review."}]}]}'
      shellbrain concept update --json '{"schema_version":"concept.v1","actions":[{"type":"add_relation","subject":"deposit-addresses","predicate":"depends_on","object":"refunds","evidence":[{"kind":"transcript","transcript_ref":"evt-123"}]}]}'
      shellbrain concept update --json '{"schema_version":"concept.v1","actions":[{"type":"ensure_anchor","kind":"file","locator":{"path":"app/refunds.py"}}]}'
      shellbrain concept update --json '{"schema_version":"concept.v1","actions":[{"type":"add_grounding","concept":"deposit-addresses","role":"implementation","anchor":{"kind":"symbol","locator":{"path":"app/refunds.py","symbol":"resolve_deposit_address"}},"evidence":[{"kind":"transcript","transcript_ref":"evt-124"}]}]}'
      shellbrain concept update --json '{"schema_version":"concept.v1","actions":[{"type":"link_memory","concept":"deposit-addresses","role":"example_of","memory_id":"mem-123","evidence":[{"kind":"memory","memory_id":"mem-123"}]}]}'
    """
)

_CONCEPT_SHOW_HELP = dedent(
    """\
    Internal recall-agent read-only endpoint for inspecting one concept.

    Use this for progressive disclosure after `read` returns a concept ref that may
    affect the synthesis brief. Working agents should call `recall`, not this command.

    Example:
      shellbrain concept show --json '{"schema_version":"concept.v1","concept":"deposit-addresses","include":["claims","relations","groundings","memory_links"]}'
    """
)

_EVENTS_HELP = dedent(
    """\
    Internal-agent endpoint for inspecting the newest repo-matching host session.

    `events` performs an inline transcript sync before returning normalized episodic evidence.
    Recall agents should run this before private reads. Session knowledge-builder agents
    should use this to inspect exact episode evidence and use returned ids as
    `evidence_refs`.

    Examples:
      shellbrain events --json '{"limit":10}'
      shellbrain events --json '{"episode_id":"episode-123","after_seq":3,"up_to_seq":8}'
    """
)

_UPDATE_HELP = dedent(
    """\
    Update one existing Shellbrain entry.

    Update types:
      - `update_lifecycle`
      - `utility_vote` (`-1.0` to `1.0`; negative = unhelpful, `0.0` = neutral, positive = helpful)
      - `fact_update_link`
      - `association_link`

    Examples:
      shellbrain memory update --json '{"memory_id":"mem-older-solution","update":{"type":"utility_vote","problem_id":"mem-problem-123","vote":1.0,"evidence_refs":["evt-456"]}}'
      shellbrain memory update --json '{"memory_id":"mem-old-fact","update":{"type":"fact_update_link","old_fact_id":"mem-old-fact","new_fact_id":"mem-new-fact","evidence_refs":["evt-457"]}}'
      shellbrain memory update --json '{"memory_id":"mem-solution","update":{"type":"association_link","to_memory_id":"mem-fact","relation_type":"depends_on","confidence":0.8,"salience":0.6,"evidence_refs":["evt-458"]}}'
      shellbrain memory update --json '{"memory_id":"mem-stale","update":{"type":"update_lifecycle","status":"superseded","superseded_by_id":"mem-new-fact","rationale":"Replaced by later implementation evidence.","actor":"manual","evidence":[{"kind":"manual","note":"Verified during review."}]}}'
    """
)

_SCENARIO_HELP = dedent(
    """\
    Internal knowledge-builder endpoint for recording bounded problem-solving runs.

    `scenario record` writes a problem_run, not a memory. It links exact episode
    evidence to existing problem/solution memories so Shellbrain can measure
    problem windows, token usage, and recall ROI.

    Record the run only after durable problem/solution memory boundaries exist.
    Shellbrain derives opened_at and closed_at from the referenced episode events.

    Outcomes:
      - `solved`: requires `problem_memory_id`, `solution_memory_id`,
        `opened_event_id`, and `closed_event_id`
      - `abandoned`: requires `problem_memory_id`, `opened_event_id`, and
        `closed_event_id`; do not include `solution_memory_id`

    Examples:
      shellbrain scenario record --json '{"schema_version":"scenario.v1","scenario":{"episode_id":"episode-123","outcome":"solved","problem_memory_id":"mem-problem-1","solution_memory_id":"mem-solution-1","opened_event_id":"evt-10","closed_event_id":"evt-42"}}'
      shellbrain scenario record --json '{"schema_version":"scenario.v1","scenario":{"episode_id":"episode-123","outcome":"abandoned","problem_memory_id":"mem-problem-1","opened_event_id":"evt-10","closed_event_id":"evt-42"}}'
    """
)

_ADMIN_HELP = "Manage backups and select the recall provider."


_UPGRADE_HELP = (
    "Upgrade the package and automatically repair runtime setup and host integrations."
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

    subparsers.add_parser(
        "upgrade",
        help="Upgrade Shellbrain and repair runtime setup through the hosted upgrader.",
        description="Upgrade Shellbrain through the hosted upgrade script and repair runtime setup.",
        epilog=_UPGRADE_HELP,
        formatter_class=_HelpFormatter,
    )

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
        description="Return a compact synthesis brief from targeted Shellbrain retrieval.",
        epilog=_RECALL_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(recall_parser, suppress_default=True)
    recall_parser.add_argument("query", help="Natural-language recall query.")

    snapshot_parser = subparsers.add_parser(
        "snapshot",
        help="Capture current repo state into repo-local shadow Git.",
        description="Capture exact repo code state into .shellbrain/shadow.git and store metadata for later solution deltas.",
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(snapshot_parser, suppress_default=True)

    concept_parser = subparsers.add_parser(
        "concept",
        help="Internal concept graph endpoints.",
        description="Inspect, add, or update typed concept graph substrate records.",
        epilog=_CONCEPT_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(concept_parser, suppress_default=True)
    concept_subparsers = concept_parser.add_subparsers(
        dest="concept_command", required=True, metavar="concept-command"
    )
    concept_show_parser = concept_subparsers.add_parser(
        "show",
        help="Inspect one concept graph record.",
        description="Inspect one concept graph record and requested facets.",
        epilog=_CONCEPT_SHOW_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(concept_show_parser, suppress_default=True)
    _add_payload_arguments(concept_show_parser)
    concept_add_parser = concept_subparsers.add_parser(
        "add",
        help="Add concept graph records.",
        description="Add typed concept graph records.",
        epilog=_CONCEPT_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(concept_add_parser, suppress_default=True)
    _add_payload_arguments(concept_add_parser)
    concept_update_parser = concept_subparsers.add_parser(
        "update",
        help="Update concept graph records.",
        description="Update typed concept graph records.",
        epilog=_CONCEPT_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(concept_update_parser, suppress_default=True)
    _add_payload_arguments(concept_update_parser)

    events_parser = subparsers.add_parser(
        "events",
        help="Inspect recent host transcript events.",
        description="Return recent episode events from the newest repo-matching host session.",
        epilog=_EVENTS_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(events_parser, suppress_default=True)
    _add_payload_arguments(events_parser)

    memory_parser = subparsers.add_parser(
        "memory",
        help="Internal knowledge-builder memory write endpoints.",
        description="Add or update durable Shellbrain memories from evidence.",
        epilog=_CREATE_HELP + "\n" + _UPDATE_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(memory_parser, suppress_default=True)
    memory_subparsers = memory_parser.add_subparsers(
        dest="memory_command", required=True, metavar="memory-command"
    )
    memory_add_parser = memory_subparsers.add_parser(
        "add",
        help="Add one durable memory from explicit evidence.",
        description="Add one durable memory from explicit evidence.",
        epilog=_CREATE_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(memory_add_parser, suppress_default=True)
    _add_payload_arguments(memory_add_parser)
    memory_update_parser = memory_subparsers.add_parser(
        "update",
        help="Update one durable memory from explicit evidence.",
        description="Update one durable memory from explicit evidence.",
        epilog=_UPDATE_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(memory_update_parser, suppress_default=True)
    _add_payload_arguments(memory_update_parser)

    scenario_parser = subparsers.add_parser(
        "scenario",
        help="Internal knowledge-builder problem-run endpoint.",
        description="Record bounded problem-solving runs from episode evidence into problem_runs.",
        epilog=_SCENARIO_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(scenario_parser, suppress_default=True)
    scenario_subparsers = scenario_parser.add_subparsers(
        dest="scenario_command", required=True, metavar="scenario-command"
    )
    scenario_record_parser = scenario_subparsers.add_parser(
        "record",
        help="Record one solved or abandoned problem-solving run.",
        description="Record one bounded problem-solving run into problem_runs from existing memories and episode events.",
        epilog=_SCENARIO_HELP,
        formatter_class=_HelpFormatter,
    )
    _add_repo_context_arguments(scenario_record_parser, suppress_default=True)
    _add_payload_arguments(scenario_record_parser)

    admin_parser = subparsers.add_parser(
        "admin",
        help="Backups and recall provider settings.",
        description="Manage backups and recall synthesis settings.",
        epilog=_ADMIN_HELP,
        formatter_class=_HelpFormatter,
    )
    admin_subparsers = admin_parser.add_subparsers(
        dest="admin_command", required=True, metavar="admin-command"
    )
    backup_parser = admin_subparsers.add_parser(
        "backup",
        help="Create, list, verify, and restore Shellbrain logical backups.",
        description="Create, list, verify, and restore Shellbrain logical backups.",
        epilog=_BACKUP_HELP,
        formatter_class=_HelpFormatter,
    )
    backup_subparsers = backup_parser.add_subparsers(
        dest="backup_command", required=True, metavar="backup-command"
    )
    backup_subparsers.add_parser(
        "create", help="Create one logical backup for the configured database."
    )
    backup_subparsers.add_parser("list", help="List available backup manifests.")
    verify_parser = backup_subparsers.add_parser(
        "verify", help="Verify one backup artifact, defaulting to the newest."
    )
    verify_parser.add_argument(
        "--backup-id",
        help="Optional backup id to verify. Defaults to the newest backup.",
    )
    restore_parser = backup_subparsers.add_parser(
        "restore", help="Restore one backup into a fresh scratch database."
    )
    restore_parser.add_argument(
        "--target-db",
        required=True,
        help="Name of the scratch restore database to create.",
    )
    restore_parser.add_argument(
        "--backup-id",
        help="Optional backup id to restore. Defaults to the newest backup.",
    )
    recall_parser = admin_subparsers.add_parser(
        "recall", help="Configure recall synthesis."
    )
    recall_subparsers = recall_parser.add_subparsers(
        dest="recall_command", required=True
    )
    provider_parser = recall_subparsers.add_parser(
        "provider", help="Choose the recall provider (default: codex)."
    )
    provider_parser.add_argument("provider", choices=get_args(RecallProvider))
    return parser


def _add_repo_context_arguments(
    parser: argparse.ArgumentParser, *, suppress_default: bool = False
) -> None:
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


def _add_payload_arguments(
    parser: argparse.ArgumentParser, *, required: bool = True
) -> None:
    """Require one JSON payload source for an operational subcommand."""

    payload_group = parser.add_mutually_exclusive_group(required=required)
    payload_group.add_argument("--json", dest="json_text", help="Inline JSON payload.")
    payload_group.add_argument(
        "--json-file", dest="json_file", help="Path to a JSON payload file."
    )
