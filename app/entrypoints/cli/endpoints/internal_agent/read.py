"""Internal-agent endpoint for raw Shellbrain reads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.startup.operations import handle_read
from app.startup.read_policy import get_read_hydration_defaults
from app.startup.runtime_context import get_operation_telemetry_context
from app.startup.use_cases import get_uow_factory


def run(payload: dict[str, Any], *, repo_id: str, repo_root: Path) -> dict[str, Any]:
    """Return raw read context for internal agents."""

    return handle_read(
        payload,
        uow_factory=get_uow_factory(),
        inferred_repo_id=repo_id,
        defaults=get_read_hydration_defaults(),
        telemetry_context=get_operation_telemetry_context(),
        repo_root=repo_root,
    )
