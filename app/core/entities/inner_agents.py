"""Core settings for bounded inner-agent execution."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


InnerAgentName = Literal["build_context", "build_knowledge", "teach", "wiki_summary"]
InnerAgentProviderName = str
InnerAgentReasoningLevel = Literal["none", "minimal", "low", "medium", "high", "xhigh"]
BuildContextStrategy = Literal[
    "deterministic_synthesis", "deterministic_only", "autonomous"
]
TokenCaptureQuality = Literal["exact", "estimated"]
InnerAgentRunStatus = Literal[
    "ok",
    "no_context",
    "provider_unavailable",
    "timeout",
    "invalid_output",
    "error",
]


class BuildContextSettings(_StrictModel):
    """Typed model/runtime settings for the build_context recall agent."""

    strategy: BuildContextStrategy = "deterministic_synthesis"
    provider: InnerAgentProviderName = Field(min_length=1)
    model: str = Field(min_length=1)
    reasoning: InnerAgentReasoningLevel
    timeout_seconds: int = Field(ge=1, le=600)
    max_private_reads: int = Field(default=0, ge=0, le=10)
    max_brief_tokens: int | None = Field(default=None, ge=1, le=100_000)


class BuildKnowledgeSettings(_StrictModel):
    """Typed model/runtime settings for the build_knowledge maintenance agent."""

    provider: InnerAgentProviderName = Field(min_length=1)
    model: str = Field(min_length=1)
    reasoning: InnerAgentReasoningLevel
    timeout_seconds: int = Field(ge=1, le=1200)
    max_shellbrain_reads: int = Field(default=8, ge=1, le=50)
    max_code_files: int = Field(default=24, ge=0, le=200)
    max_write_commands: int = Field(default=20, ge=1, le=200)
    idle_stable_seconds: int = Field(default=900, ge=60, le=86_400)
    running_run_stale_seconds: int = Field(default=3600, ge=60, le=86_400)


class TeachKnowledgeSettings(_StrictModel):
    """Typed model/runtime settings for explicit teaching consolidation."""

    provider: InnerAgentProviderName = Field(min_length=1)
    model: str = Field(min_length=1)
    reasoning: InnerAgentReasoningLevel
    timeout_seconds: int = Field(ge=1, le=1200)
    max_shellbrain_reads: int = Field(default=6, ge=1, le=50)
    max_code_files: int = Field(default=5, ge=0, le=200)
    max_write_commands: int = Field(default=12, ge=1, le=200)


class WikiSummarySettings(_StrictModel):
    """Typed model/runtime settings for generated wiki summaries."""

    provider: InnerAgentProviderName = Field(min_length=1)
    model: str = Field(min_length=1)
    reasoning: InnerAgentReasoningLevel
    timeout_seconds: int = Field(ge=1, le=1200)
    prompt_version: str = Field(default="wiki-summary.v1", min_length=1)
    max_summary_chars: int = Field(default=900, ge=100, le=4000)
    running_refresh_stale_seconds: int = Field(default=3600, ge=60, le=86_400)
    startup_batch_limit: int = Field(default=20, ge=0, le=200)
    periodic_batch_limit: int = Field(default=5, ge=0, le=100)
    periodic_seconds: int = Field(default=300, ge=30, le=86_400)


InnerAgentSettings = BuildContextSettings
