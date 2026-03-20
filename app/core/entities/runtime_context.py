"""Per-invocation runtime context shared across CLI handlers."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.contracts.errors import ErrorDetail
from app.core.entities.identity import CallerIdentity


@dataclass(frozen=True)
class RuntimeContext:
    """Per-command context captured in CLI main and consumed by handlers."""

    invocation_id: str
    repo_root: str
    no_sync: bool = False
    caller_identity: CallerIdentity | None = None
    caller_identity_error: ErrorDetail | None = None
