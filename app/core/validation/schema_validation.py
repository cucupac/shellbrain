"""This module defines schema-level validation helpers for strict request contracts."""

from typing import Any

from pydantic import ValidationError

from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.contracts.requests import MemoryCreateRequest, MemoryReadRequest, MemoryUpdateRequest


def _format_validation_errors(exc: ValidationError) -> list[ErrorDetail]:
    """This function converts Pydantic validation errors into contract error details."""

    details: list[ErrorDetail] = []
    for item in exc.errors():
        path = ".".join(str(segment) for segment in item.get("loc", ()))
        details.append(
            ErrorDetail(
                code=ErrorCode.SCHEMA_ERROR,
                message=item.get("msg", "Schema validation failed"),
                field=path or None,
            )
        )
    return details


def validate_create_schema(payload: dict[str, Any]) -> tuple[MemoryCreateRequest | None, list[ErrorDetail]]:
    """This function validates and parses create payloads into the strict create contract."""

    try:
        return MemoryCreateRequest.model_validate(payload), []
    except ValidationError as exc:
        return None, _format_validation_errors(exc)


def validate_read_schema(payload: dict[str, Any]) -> tuple[MemoryReadRequest | None, list[ErrorDetail]]:
    """This function validates and parses read payloads into the strict read contract."""

    try:
        return MemoryReadRequest.model_validate(payload), []
    except ValidationError as exc:
        return None, _format_validation_errors(exc)


def validate_update_schema(payload: dict[str, Any]) -> tuple[MemoryUpdateRequest | None, list[ErrorDetail]]:
    """This function validates and parses update payloads into the strict update contract."""

    try:
        return MemoryUpdateRequest.model_validate(payload), []
    except ValidationError as exc:
        return None, _format_validation_errors(exc)
