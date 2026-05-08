"""Worker-facing memory command dispatch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.startup.operations import handle_concept, handle_create, handle_events, handle_read, handle_recall, handle_update


def dispatch_operation_command(
    command: str,
    payload: dict[str, Any],
    *,
    repo_id: str,
    repo_root: Path,
) -> dict[str, Any]:
    """Resolve runtime dependencies lazily and execute one operational command."""

    from app.startup.create_policy import get_create_hydration_defaults
    from app.startup.read_policy import get_read_hydration_defaults
    from app.startup.runtime_context import get_operation_telemetry_context
    from app.startup.use_cases import get_embedding_model, get_embedding_provider_factory, get_uow_factory

    uow_factory = get_uow_factory()
    if command == "create":
        return handle_create(
            payload,
            uow_factory=uow_factory,
            embedding_provider_factory=get_embedding_provider_factory(),
            embedding_model=get_embedding_model(),
            inferred_repo_id=repo_id,
            defaults=get_create_hydration_defaults(),
            telemetry_context=get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "read":
        return handle_read(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=repo_id,
            defaults=get_read_hydration_defaults(),
            telemetry_context=get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "recall":
        return handle_recall(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=repo_id,
            telemetry_context=get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "concept":
        return handle_concept(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=repo_id,
            telemetry_context=get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "update":
        return handle_update(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=repo_id,
            telemetry_context=get_operation_telemetry_context(),
            repo_root=repo_root,
        )
    if command == "events":
        return handle_events(
            payload,
            uow_factory=uow_factory,
            inferred_repo_id=repo_id,
            repo_root=repo_root,
            telemetry_context=get_operation_telemetry_context(),
        )
    raise ValueError(f"Unsupported command: {command}")
