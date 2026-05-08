"""Legacy CLI aliases for pre-audience command names."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.entrypoints.cli.endpoints.internal_agent.concepts.update import run as run_concept_batch
from app.entrypoints.cli.endpoints.internal_agent.memories.add import run as run_memory_add
from app.entrypoints.cli.endpoints.internal_agent.memories.update import run as run_memory_update


def run_create_alias(payload: dict[str, Any], *, repo_id: str, repo_root: Path) -> dict[str, Any]:
    """Legacy `create` alias for `memory add`."""

    return run_memory_add(payload, repo_id=repo_id, repo_root=repo_root)


def run_update_alias(payload: dict[str, Any], *, repo_id: str, repo_root: Path) -> dict[str, Any]:
    """Legacy `update` alias for `memory update`."""

    return run_memory_update(payload, repo_id=repo_id, repo_root=repo_root)


def run_concept_alias(payload: dict[str, Any], *, repo_id: str, repo_root: Path) -> dict[str, Any]:
    """Legacy `concept` graph batch endpoint."""

    return run_concept_batch(payload, repo_id=repo_id, repo_root=repo_root)
