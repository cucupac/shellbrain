"""Internal runtime context helpers for per-command telemetry capture."""

from __future__ import annotations

from contextvars import ContextVar, Token

from shellbrain.core.entities.telemetry import OperationDispatchTelemetryContext


_OPERATION_TELEMETRY_CONTEXT: ContextVar[OperationDispatchTelemetryContext | None] = ContextVar(
    "shellbrain_operation_telemetry_context",
    default=None,
)


def get_operation_telemetry_context() -> OperationDispatchTelemetryContext | None:
    """Return the current command-level telemetry context when one exists."""

    return _OPERATION_TELEMETRY_CONTEXT.get()


def set_operation_telemetry_context(
    context: OperationDispatchTelemetryContext,
) -> Token[OperationDispatchTelemetryContext | None]:
    """Install one command-level telemetry context for the current execution flow."""

    return _OPERATION_TELEMETRY_CONTEXT.set(context)


def reset_operation_telemetry_context(token: Token[OperationDispatchTelemetryContext | None]) -> None:
    """Restore the previous telemetry context after a command finishes."""

    _OPERATION_TELEMETRY_CONTEXT.reset(token)
