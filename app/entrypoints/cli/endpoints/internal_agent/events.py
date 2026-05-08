"""Internal-agent endpoint for episodic evidence reads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.entrypoints.cli.protocol.operation_requests import prepare_events_request
from app.startup.agent_operations import handle_events
from app.startup.runtime_context import get_operation_telemetry_context
from app.startup.use_cases import get_uow_factory


def run(payload: dict[str, Any], *, repo_id: str, repo_root: Path) -> dict[str, Any]:
    """Return recent episode events for internal-agent evidence selection."""

    prepared = prepare_events_request(payload, inferred_repo_id=repo_id)
    return handle_events(
        prepared.request,
        uow_factory=get_uow_factory(),
        inferred_repo_id=repo_id,
        validation_errors=prepared.errors,
        validation_error_stage=prepared.error_stage,
        repo_root=repo_root,
        telemetry_context=get_operation_telemetry_context(),
    )
