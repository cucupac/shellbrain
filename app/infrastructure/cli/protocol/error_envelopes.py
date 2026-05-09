"""CLI protocol error envelope helpers."""

from app.core.contracts.errors import ErrorDetail
from app.infrastructure.cli.handlers.result_envelopes import error_envelope


def error_response(errors: list[ErrorDetail]) -> dict:
    """Build the standard operation error response envelope."""

    return error_envelope(errors)
