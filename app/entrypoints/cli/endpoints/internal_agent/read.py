"""Internal-agent endpoint for raw Shellbrain reads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.entrypoints.cli.protocol.operation_requests import prepare_read_request
from app.startup.agent_operations import handle_read
from app.startup.read_policy import get_read_hydration_defaults
from app.startup.runtime_context import get_operation_telemetry_context
from app.startup.use_cases import get_uow_factory


def run(payload: dict[str, Any], *, repo_id: str, repo_root: Path) -> dict[str, Any]:
    """Return raw read context for internal agents."""

    prepared = prepare_read_request(
        payload,
        inferred_repo_id=repo_id,
        defaults=get_read_hydration_defaults(),
    )
    return handle_read(
        prepared.request,
        uow_factory=get_uow_factory(),
        inferred_repo_id=repo_id,
        validation_errors=prepared.errors,
        validation_error_stage=prepared.error_stage,
        requested_limit=prepared.requested_limit,
        telemetry_context=get_operation_telemetry_context(),
        repo_root=repo_root,
    )
