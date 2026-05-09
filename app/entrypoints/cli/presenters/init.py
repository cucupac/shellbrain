"""Human-facing Shellbrain init output."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def render_success_lines(
    *,
    outcome: str,
    config: Any,
    registration: Any | None,
    notes: list[str],
    runtime_mode_managed_local: str,
    identity_strength_weak_local: str,
    fingerprint_summary: Callable[[str], dict[str, Any]],
) -> list[str]:
    """Render the init success summary lines without the outcome prefix."""

    del outcome
    if config.runtime_mode == runtime_mode_managed_local and config.managed is not None:
        runtime_line = f"Managed instance: {config.managed.container_name} ({config.managed.host}:{config.managed.port})"
    else:
        summary = fingerprint_summary(config.database.admin_dsn)
        runtime_line = f"External database: {summary['host']}:{summary['port']}/{summary['database']}"
    lines = [
        runtime_line,
        f"Embeddings: {config.embeddings.readiness_state}",
        f"Backups: {config.backups.root}",
    ]
    if registration is None:
        lines.append(
            "Repo registration: deferred until first Shellbrain use inside a repo."
        )
        lines.append(
            'Next: from inside a repo, run shellbrain read --json \'{"query":"What prior Shellbrain context matters for this task?","kinds":["problem","solution","failed_tactic","fact","preference","change"]}\''
        )
    else:
        lines.insert(1, f"Repo: {registration.repo_id}")
        if registration.identity_strength == identity_strength_weak_local:
            lines.insert(
                2,
                "Repo identity is weak-local and will change if this directory moves. Use --repo-id for a durable override.",
            )
        lines.append(
            'Next: shellbrain read --json \'{"query":"What prior Shellbrain context matters for this task?","kinds":["problem","solution","failed_tactic","fact","preference","change"]}\''
        )
    lines.extend(notes)
    return lines
