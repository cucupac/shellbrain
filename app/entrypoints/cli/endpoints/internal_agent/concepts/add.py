"""Internal-agent endpoint for concept graph additions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.entrypoints.cli.protocol.operation_requests import prepare_concept_request
from app.startup.agent_operations import handle_concept
from app.startup.runtime_context import get_operation_telemetry_context
from app.startup.use_cases import get_uow_factory


def run(payload: dict[str, Any], *, repo_id: str, repo_root: Path) -> dict[str, Any]:
    """Apply concept graph additions from a typed concept payload."""

    prepared = prepare_concept_request(payload, inferred_repo_id=repo_id)
    return handle_concept(
        prepared.request,
        uow_factory=get_uow_factory(),
        inferred_repo_id=repo_id,
        validation_errors=prepared.errors,
        validation_error_stage=prepared.error_stage,
        telemetry_context=get_operation_telemetry_context(),
        repo_root=repo_root,
    )
