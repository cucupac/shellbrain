"""Internal-agent endpoint for concept graph updates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.entrypoints.cli.endpoints.internal_agent.concepts.add import run as _run_concept_apply


def run(payload: dict[str, Any], *, repo_id: str, repo_root: Path) -> dict[str, Any]:
    """Apply concept graph updates from a typed concept payload."""

    return _run_concept_apply(payload, repo_id=repo_id, repo_root=repo_root)
