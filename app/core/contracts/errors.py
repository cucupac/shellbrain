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
    HOST_IDENTITY_UNAVAILABLE = "host_identity_unavailable"
    HOST_IDENTITY_UNSUPPORTED = "host_identity_unsupported"
    HOST_IDENTITY_DRIFTED = "host_identity_drifted"
    HOST_HOOK_MISSING = "host_hook_missing"
    TRANSCRIPT_SOURCE_NOT_FOUND = "transcript_source_not_found"


class ErrorDetail(BaseModel):
    """This model defines a structured error payload entry."""

    code: ErrorCode
    message: str
    field: str | None = None
