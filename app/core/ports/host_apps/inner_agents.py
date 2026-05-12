"""Inner-agent provider ports implemented by host-app infrastructure."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.core.entities.inner_agents import (
    InnerAgentName,
    InnerAgentProviderName,
    InnerAgentReasoningLevel,
    InnerAgentRunStatus,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InnerAgentRunRequest(_StrictModel):
    """One bounded inner-agent synthesis request."""

    agent_name: InnerAgentName
    provider: InnerAgentProviderName
    model: str = Field(min_length=1)
    reasoning: InnerAgentReasoningLevel
    timeout_seconds: int = Field(ge=1, le=600)
    max_candidate_tokens: int = Field(ge=1, le=200_000)
    max_brief_tokens: int | None = Field(default=None, ge=1, le=100_000)
    query: str = Field(min_length=1)
    current_problem: dict[str, str | None] | None = None
    repo_root: str | None = None
    candidate_context: dict[str, Any]
    expansion_handles: list[dict[str, Any]] = Field(default_factory=list)


class InnerAgentRunResult(_StrictModel):
    """Provider-neutral result from an inner-agent run."""

    status: InnerAgentRunStatus
    provider: InnerAgentProviderName
    model: str
    reasoning: InnerAgentReasoningLevel
    brief: dict[str, Any] | None = None
    fallback_used: bool = False
    timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    duration_ms: int = Field(default=0, ge=0)
    input_token_estimate: int | None = Field(default=None, ge=0)
    output_token_estimate: int | None = Field(default=None, ge=0)
    private_read_count: int = Field(default=0, ge=0)
    concept_expansion_count: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_message: str | None = None
    requested_expansions: list[dict[str, Any]] = Field(default_factory=list)


class IInnerAgentRunner(Protocol):
    """Behavior protocol for bounded inner-agent synthesis providers."""

    def run(self, request: InnerAgentRunRequest) -> InnerAgentRunResult:
        """Run one inner-agent request and return a provider-neutral result."""
