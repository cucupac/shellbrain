"""Internal-agent endpoint for adding durable memories."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.entrypoints.cli.protocol.operation_requests import prepare_create_request
from app.startup.create_policy import get_create_hydration_defaults
from app.startup.agent_operations import handle_create
from app.startup.runtime_context import get_operation_telemetry_context
from app.startup.use_cases import get_embedding_model, get_embedding_provider_factory, get_uow_factory


def run(payload: dict[str, Any], *, repo_id: str, repo_root: Path) -> dict[str, Any]:
    """Create one durable memory from an internal-agent payload."""

    prepared = prepare_create_request(
        payload,
        inferred_repo_id=repo_id,
        defaults=get_create_hydration_defaults(),
    )
    return handle_create(
        prepared.request,
        uow_factory=get_uow_factory(),
        embedding_provider_factory=get_embedding_provider_factory(),
        embedding_model=get_embedding_model(),
        inferred_repo_id=repo_id,
        validation_errors=prepared.errors,
        validation_error_stage=prepared.error_stage,
        telemetry_context=get_operation_telemetry_context(),
        repo_root=repo_root,
    )
