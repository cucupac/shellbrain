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


def error_response(errors: list[ErrorDetail]) -> dict:
    """Build a standardized error response envelope."""

    return error_envelope(errors)


def ok_envelope(result: Any = None) -> dict:
    """Wrap core payload data in the standard success envelope."""

    if result is None:
        data: dict[str, Any] = {}
    elif isinstance(result, dict):
        data = dict(result)
    elif hasattr(result, "to_response_data"):
        data = dict(result.to_response_data())
    elif hasattr(result, "data") and isinstance(result.data, dict):
        data = dict(result.data)
    elif isinstance(result, BaseModel):
        data = result.model_dump(mode="python")
    else:
        data = {"result": result}
    return OperationResult(status="ok", data=data).model_dump(mode="python")


class error_envelope:
    """Callable error envelope constructor with typed-exception support."""

    def __new__(
        cls,
        errors: list[ErrorDetail] | tuple[ErrorDetail, ...],
        *,
        stage: str | None = None,
    ) -> dict:
        del stage
        return OperationResult(status="error", errors=list(errors)).model_dump(
            mode="python"
        )

    @classmethod
    def from_exception(cls, exc: Exception) -> dict:
        errors = getattr(exc, "errors", None)
        if isinstance(errors, list) and all(
            isinstance(error, ErrorDetail) for error in errors
        ):
            return OperationResult(status="error", errors=errors).model_dump(
                mode="python"
            )
        return OperationResult(
            status="error",
            errors=[ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))],
        ).model_dump(mode="python")


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
