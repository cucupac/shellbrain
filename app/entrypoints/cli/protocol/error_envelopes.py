"""CLI protocol error envelope helpers."""

from app.core.contracts.errors import ErrorDetail
from app.core.contracts.responses import OperationResult


def error_response(errors: list[ErrorDetail]) -> dict:
    """Build the standard operation error response envelope."""

    return OperationResult(status="error", errors=errors).model_dump(mode="python")
