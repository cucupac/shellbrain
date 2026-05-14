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
from app.core.entities.knowledge_builder import (
    KnowledgeBuildRunStatus,
    KnowledgeBuildTrigger,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InnerAgentRunRequest(_StrictModel):
    """One autonomous read-only inner-agent synthesis request."""

    agent_name: InnerAgentName
    provider: InnerAgentProviderName
    model: str = Field(min_length=1)
    reasoning: InnerAgentReasoningLevel
    timeout_seconds: int = Field(ge=1, le=600)
    max_private_reads: int = Field(default=0, ge=0, le=10)
    max_candidate_tokens: int = Field(ge=1, le=200_000)
    max_brief_tokens: int | None = Field(default=None, ge=1, le=100_000)
    query: str = Field(min_length=1)
    current_problem: dict[str, str]
    repo_root: str | None = None


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
    read_trace: dict[str, Any] = Field(default_factory=dict)


class BuildKnowledgeAgentRequest(_StrictModel):
    """One autonomous build_knowledge provider request."""

    agent_name: InnerAgentName = "build_knowledge"
    provider: InnerAgentProviderName
    model: str = Field(min_length=1)
    reasoning: InnerAgentReasoningLevel
    timeout_seconds: int = Field(ge=1, le=1200)
    repo_id: str = Field(min_length=1)
    repo_root: str
    episode_id: str = Field(min_length=1)
    trigger: KnowledgeBuildTrigger
    event_watermark: int = Field(ge=0)
    previous_event_watermark: int | None = Field(default=None, ge=0)
    max_shellbrain_reads: int = Field(ge=1, le=50)
    max_code_files: int = Field(ge=0, le=200)
    max_write_commands: int = Field(ge=1, le=200)


class BuildKnowledgeAgentResult(_StrictModel):
    """Provider-neutral result from one build_knowledge run."""

    status: KnowledgeBuildRunStatus
    provider: InnerAgentProviderName
    model: str
    reasoning: InnerAgentReasoningLevel
    timeout_seconds: int | None = Field(default=None, ge=1, le=1200)
    duration_ms: int = Field(default=0, ge=0)
    input_token_estimate: int | None = Field(default=None, ge=0)
    output_token_estimate: int | None = Field(default=None, ge=0)
    write_count: int = Field(default=0, ge=0)
    skipped_item_count: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_message: str | None = None
    run_summary: str | None = None
    read_trace: dict[str, Any] = Field(default_factory=dict)
    code_trace: dict[str, Any] = Field(default_factory=dict)


class IInnerAgentRunner(Protocol):
    """Behavior protocol for bounded inner-agent synthesis providers."""

    def run(self, request: InnerAgentRunRequest) -> InnerAgentRunResult:
        """Run one inner-agent request and return a provider-neutral result."""


class IBuildKnowledgeAgentRunner(Protocol):
    """Behavior protocol for build_knowledge providers."""

    def run_build_knowledge(
        self, request: BuildKnowledgeAgentRequest
    ) -> BuildKnowledgeAgentResult:
        """Run one build_knowledge request and return a provider-neutral result."""
