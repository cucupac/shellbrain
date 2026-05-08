"""Error envelope helpers for agent operation workflows."""

from __future__ import annotations

from app.core.contracts.errors import ErrorDetail
from app.core.contracts.responses import OperationResult


class ReturnHandledError(Exception):
    """Control-flow exception for already-materialized operation responses."""


def error_response(errors: list[ErrorDetail]) -> dict:
    """Build a standardized error response envelope."""

    return OperationResult(status="error", errors=errors).model_dump(mode="python")


def dump_errors(errors: list[ErrorDetail]) -> list[dict]:
    """Render structured errors into plain dicts for telemetry stage mapping."""

    return [error.model_dump(mode="python") for error in errors]
