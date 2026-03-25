"""Shared bootstrap exceptions for Shellbrain init flows."""

from __future__ import annotations


class InitDependencyError(RuntimeError):
    """Raised when one bootstrap dependency is missing."""


class InitConflictError(RuntimeError):
    """Raised when runtime resources cannot be adopted safely."""


class InitLockError(RuntimeError):
    """Raised when the machine init lock cannot be acquired safely."""
