"""CLI error response envelope helpers."""

from app.core.errors import ErrorDetail
from app.entrypoints.cli.handlers.result_envelopes import error_envelope


def error_response(errors: list[ErrorDetail]) -> dict:
    """Build the standard operation error response envelope."""

    return error_envelope(errors)
