"""Internal runtime context helpers for per-command telemetry capture."""

from __future__ import annotations

from contextvars import ContextVar, Token

from shellbrain.core.entities.runtime_context import RuntimeContext


_OPERATION_TELEMETRY_CONTEXT: ContextVar[RuntimeContext | None] = ContextVar(
    "shellbrain_operation_telemetry_context",
    default=None,
)


def get_operation_telemetry_context() -> RuntimeContext | None:
    """Return the current command-level telemetry context when one exists."""

    return _OPERATION_TELEMETRY_CONTEXT.get()


def set_operation_telemetry_context(
    context: RuntimeContext,
) -> Token[RuntimeContext | None]:
    """Install one command-level telemetry context for the current execution flow."""

    return _OPERATION_TELEMETRY_CONTEXT.set(context)


def reset_operation_telemetry_context(token: Token[RuntimeContext | None]) -> None:
    """Restore the previous telemetry context after a command finishes."""

    _OPERATION_TELEMETRY_CONTEXT.reset(token)
