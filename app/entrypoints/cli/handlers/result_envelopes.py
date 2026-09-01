"""Result envelope helpers for command handlers."""

from __future__ import annotations

from typing import Any, Literal

from app.core.errors import ErrorCode, ErrorDetail
from pydantic import BaseModel, Field


class OperationResult(BaseModel):
    """Audience-shaped operation envelope owned by handlers."""

    status: Literal["ok", "error"]
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[ErrorDetail] = Field(default_factory=list)


class ReturnHandledError(Exception):
    """Control-flow exception for already-materialized operation responses."""


def error_response(errors: list[ErrorDetail] | tuple[ErrorDetail, ...]) -> dict:
    """Build a standardized error response envelope."""

    return OperationResult(status="error", errors=list(errors)).model_dump(
        mode="python"
    )


def ok_envelope(result: Any = None) -> dict:
    """Wrap core payload data in the standard success envelope."""

    if result is None:
        data: dict[str, Any] = {}
    elif isinstance(result, dict):
        data = dict(result)
    elif hasattr(result, "to_response_data"):
        data = dict(result.to_response_data())
    else:
        data = dict(result.data)
    return OperationResult(status="ok", data=data).model_dump(mode="python")


def dump_errors(errors: list[ErrorDetail]) -> list[dict]:
    """Render structured errors into plain dicts for telemetry stage mapping."""

    return [error.model_dump(mode="python") for error in errors]


def infer_error_stage_from_errors(
    errors: list[dict[str, Any]], *, default_stage: str
) -> str:
    """Map structured error codes to stable operation failure stages."""

    if not errors:
        return default_stage
    code = errors[0].get("code")
    normalized = code.value if isinstance(code, ErrorCode) else str(code)
    if (
        normalized == ErrorCode.SCHEMA_ERROR.value
        and default_stage == "schema_validation"
    ):
        return "schema_validation"
    if (
        normalized == ErrorCode.SCHEMA_ERROR.value
        and default_stage == "contract_validation"
    ):
        return "contract_validation"
    if normalized == ErrorCode.SEMANTIC_ERROR.value:
        return "semantic_validation"
    if normalized == ErrorCode.INTEGRITY_ERROR.value:
        return "integrity_validation"
    return default_stage
