"""Structured expected errors shared across core workflows."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ErrorCode(str, Enum):
    """Canonical error codes across validation and execution layers."""

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
    INNER_AGENT_ERROR = "inner_agent_error"


class ErrorDetail(BaseModel):
    """Structured error payload entry."""

    code: ErrorCode
    message: str
    field: str | None = None


class ShellbrainError(Exception):
    """Base class for typed core errors surfaced through handler envelopes."""


class DomainValidationError(ShellbrainError, ValueError):
    """Raised when core request validation fails over policies or ports."""

    def __init__(self, errors: list[ErrorDetail]) -> None:
        self.errors = errors
        super().__init__("; ".join(error.message for error in errors))
