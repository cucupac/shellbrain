"""Core caller-identity concepts used across runtime, episodes, and telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IdentityTrustLevel(str, Enum):
    """Supported caller-identity trust levels."""

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    UNSUPPORTED = "unsupported"


SUPPORTED_HOST_APPS = frozenset({"codex", "claude_code", "cursor"})


def build_canonical_caller_id(*, host_app: str, host_session_key: str, agent_key: str | None = None) -> str:
    """Build the canonical caller identifier from one host session and optional agent key."""

    canonical = f"{host_app}:{host_session_key}"
    if agent_key:
        canonical = f"{canonical}:agent:{agent_key}"
    return canonical


@dataclass(frozen=True, kw_only=True)
class CallerIdentity:
    """Canonical caller identity used to scope episodes, session state, and guidance."""

    host_app: str
    host_session_key: str
    agent_key: str | None = None
    canonical_id: str | None = None
    trust_level: IdentityTrustLevel = IdentityTrustLevel.UNTRUSTED

    def __post_init__(self) -> None:
        """Validate caller identity and fill the canonical id when omitted."""

        host_app = self.host_app.strip()
        host_session_key = self.host_session_key.strip()
        if not host_app:
            raise ValueError("host_app must be non-empty")
        if not host_session_key:
            raise ValueError("host_session_key must be non-empty")
        if host_app not in SUPPORTED_HOST_APPS:
            raise ValueError(f"host_app must be one of: {', '.join(sorted(SUPPORTED_HOST_APPS))}")
        object.__setattr__(self, "host_app", host_app)
        object.__setattr__(self, "host_session_key", host_session_key)
        if not isinstance(self.trust_level, IdentityTrustLevel):
            object.__setattr__(self, "trust_level", IdentityTrustLevel(str(self.trust_level)))
        canonical_id = build_canonical_caller_id(
            host_app=host_app,
            host_session_key=host_session_key,
            agent_key=self.agent_key,
        )
        if self.canonical_id is not None and self.canonical_id != canonical_id:
            raise ValueError("canonical_id must match host_app, host_session_key, and agent_key")
        object.__setattr__(self, "canonical_id", canonical_id)
