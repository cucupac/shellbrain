"""CLI operation command orchestration independent of concrete startup wiring."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import os
from typing import Any

from app.core.entities.runtime_context import RuntimeContext


_INNER_AGENT_MODE_ENV = "SHELLBRAIN_INNER_AGENT_MODE"
_KNOWLEDGE_BUILD_RUN_ID_ENV = "SHELLBRAIN_KNOWLEDGE_BUILD_RUN_ID"


@dataclass(frozen=True)
class CliOperationEffects:
    """Side effects needed around one agent-facing CLI operation."""

    new_invocation_id: Callable[[], str]
    resolve_caller_identity: Callable[[], Any]
    set_operation_context: Callable[[RuntimeContext], Any]
    reset_operation_context: Callable[[Any], None]
    warn_or_fail_on_unsafe_app_role: Callable[[], None]
    ensure_repo_registration: Callable[..., None]
    maybe_start_sync: Callable[[Any], bool]
    update_operation_polling_status: Callable[..., None]


def run_cli_operation(
    *,
    command: str,
    payload: dict[str, Any],
    repo_context: Any,
    repo_id_override: str | None,
    no_sync: bool,
    dispatch_operation: Callable[[str, dict[str, Any], Any], dict[str, Any]],
    effects: CliOperationEffects,
) -> dict[str, Any]:
    """Run one hydrated operation command with startup-provided side effects."""

    caller_identity_resolution = effects.resolve_caller_identity()
    operation_context = RuntimeContext(
        invocation_id=effects.new_invocation_id(),
        repo_root=str(repo_context.repo_root),
        no_sync=no_sync,
        knowledge_build_run_id=_knowledge_build_run_id_from_env(),
        caller_identity=caller_identity_resolution.caller_identity,
        caller_identity_error=caller_identity_resolution.error,
    )
    token = effects.set_operation_context(operation_context)
    try:
        effects.warn_or_fail_on_unsafe_app_role()
        effects.ensure_repo_registration(
            repo_context=repo_context,
            repo_id_override=repo_id_override,
        )
        result = dispatch_operation(command, payload, repo_context)
        if result.get("status") == "ok":
            if no_sync:
                effects.update_operation_polling_status(
                    invocation_id=operation_context.invocation_id,
                    attempted=False,
                    started=False,
                )
            else:
                started = bool(effects.maybe_start_sync(repo_context))
                effects.update_operation_polling_status(
                    invocation_id=operation_context.invocation_id,
                    attempted=True,
                    started=started,
                )
        return result
    finally:
        effects.reset_operation_context(token)


def _knowledge_build_run_id_from_env() -> str | None:
    """Return the parent build_knowledge run id for nested builder commands."""

    mode = os.environ.get(_INNER_AGENT_MODE_ENV, "").strip()
    if mode != "build_knowledge":
        return None
    value = os.environ.get(_KNOWLEDGE_BUILD_RUN_ID_ENV, "").strip()
    return value or None
