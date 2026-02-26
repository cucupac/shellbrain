"""This module defines structured error contracts and canonical error codes."""

from enum import Enum

from pydantic import BaseModel


class ErrorCode(str, Enum):
    """This enum defines canonical error codes across validation and execution layers."""

    SCHEMA_ERROR = "schema_error"
    SEMANTIC_ERROR = "semantic_error"
    INTEGRITY_ERROR = "integrity_error"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INTERNAL_ERROR = "internal_error"


class ErrorDetail(BaseModel):
    """This model defines a structured error payload entry."""

    code: ErrorCode
    message: str
    field: str | None = None
