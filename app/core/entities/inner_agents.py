"""Core settings for bounded inner-agent execution."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


InnerAgentName = Literal["build_context", "build_knowledge"]
InnerAgentProviderName = Literal["codex"]
InnerAgentReasoningLevel = Literal["none", "minimal", "low", "medium", "high", "xhigh"]
TokenCaptureQuality = Literal["exact", "estimated"]
InnerAgentRunStatus = Literal[
    "ok",
    "no_context",
    "provider_unavailable",
    "timeout",
    "invalid_output",
    "error",
    "disabled",
]


class BuildContextSettings(_StrictModel):
    """Typed model/runtime settings for the build_context recall agent."""

    provider: InnerAgentProviderName
    model: str = Field(min_length=1)
    reasoning: InnerAgentReasoningLevel
    timeout_seconds: int = Field(ge=1, le=600)
    max_private_reads: int = Field(default=0, ge=0, le=10)
    max_candidate_tokens: int = Field(ge=1, le=200_000)
    max_brief_tokens: int | None = Field(default=None, ge=1, le=100_000)


class BuildKnowledgeSettings(_StrictModel):
    """Typed model/runtime settings for the build_knowledge maintenance agent."""

    provider: InnerAgentProviderName
    model: str = Field(min_length=1)
    reasoning: InnerAgentReasoningLevel
    timeout_seconds: int = Field(ge=1, le=1200)
    max_shellbrain_reads: int = Field(default=8, ge=1, le=50)
    max_code_files: int = Field(default=24, ge=0, le=200)
    max_write_commands: int = Field(default=20, ge=1, le=200)
    idle_stable_seconds: int = Field(default=900, ge=60, le=86_400)
    running_run_stale_seconds: int = Field(default=3600, ge=60, le=86_400)


InnerAgentSettings = BuildContextSettings
