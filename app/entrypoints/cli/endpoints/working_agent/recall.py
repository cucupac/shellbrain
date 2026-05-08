"""Working-agent endpoint for compact recall briefs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.startup.operations import handle_recall
from app.startup.runtime_context import get_operation_telemetry_context
from app.startup.use_cases import get_uow_factory


def run(payload: dict[str, Any], *, repo_id: str, repo_root: Path) -> dict[str, Any]:
    """Return one compact read-only recall brief for a working agent."""

    return handle_recall(
        payload,
        uow_factory=get_uow_factory(),
        inferred_repo_id=repo_id,
        telemetry_context=get_operation_telemetry_context(),
        repo_root=repo_root,
    )
