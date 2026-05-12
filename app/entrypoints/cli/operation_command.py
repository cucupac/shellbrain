"""Entry-point ownership for one agent-facing CLI operation command."""

from __future__ import annotations

from typing import Any

from app.entrypoints.cli.handlers.cli_operation import (
    CliOperationEffects,
    run_cli_operation,
)
from app.startup.cli_runtime import CliRuntime


def run_operation_command(
    *,
    command: str,
    payload: dict[str, Any],
    repo_context,
    repo_id_override: str | None,
    no_sync: bool,
    dispatch_operation,
    runtime: CliRuntime,
) -> dict[str, Any]:
    """Run one hydrated CLI operation with startup-supplied concrete callbacks."""

    return run_cli_operation(
        command=command,
        payload=payload,
        repo_context=repo_context,
        repo_id_override=repo_id_override,
        no_sync=no_sync,
        dispatch_operation=dispatch_operation,
        effects=CliOperationEffects(
            new_invocation_id=runtime.new_invocation_id,
            resolve_caller_identity=runtime.resolve_caller_identity,
            set_operation_context=runtime.set_operation_context,
            reset_operation_context=runtime.reset_operation_context,
            warn_or_fail_on_unsafe_app_role=runtime.warn_or_fail_on_unsafe_app_role,
            ensure_repo_registration=runtime.ensure_repo_registration,
            maybe_start_sync=runtime.maybe_start_sync,
            update_operation_polling_status=runtime.update_operation_polling_status,
        ),
    )
