"""Shared prepared-operation result container."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from app.core.contracts.errors import ErrorCode, ErrorDetail


T = TypeVar("T")


@dataclass(frozen=True)
class PreparedOperationRequest(Generic[T]):
    """Typed request plus any entrypoint validation failure details."""

    request: T | None
    errors: list[ErrorDetail]
    error_stage: str = "schema_validation"
    requested_limit: int | None = None


def hydrate_or_error(call) -> tuple[dict, ErrorDetail | None]:
    """Return hydrated payload data or convert hydration validation failures."""

    try:
        return call(), None
    except ValueError as exc:
        return {}, ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc))
