"""Core caller-identity concepts used across runtime, episodes, and telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IdentityTrustLevel(str, Enum):
    """Supported caller-identity trust levels."""

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    UNSUPPORTED = "unsupported"


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
        """Fill the canonical id when the caller omits it."""

        if self.canonical_id is None:
            object.__setattr__(
                self,
                "canonical_id",
                build_canonical_caller_id(
                    host_app=self.host_app,
                    host_session_key=self.host_session_key,
                    agent_key=self.agent_key,
                ),
            )
