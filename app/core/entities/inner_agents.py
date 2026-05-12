"""Core settings for bounded inner-agent execution."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


InnerAgentName = Literal["build_context", "build_knowledge"]
InnerAgentProviderName = Literal["codex"]
InnerAgentReasoningLevel = Literal["none", "minimal", "low", "medium", "high", "xhigh"]
InnerAgentRunStatus = Literal[
    "ok",
    "no_context",
    "provider_unavailable",
    "timeout",
    "invalid_output",
    "error",
    "disabled",
]


class InnerAgentSettings(_StrictModel):
    """Typed model/runtime settings for one inner agent."""

    provider: InnerAgentProviderName
    model: str = Field(min_length=1)
    reasoning: InnerAgentReasoningLevel
    timeout_seconds: int = Field(ge=1, le=600)
    max_private_reads: int = Field(default=0, ge=0, le=10)
    max_candidate_tokens: int = Field(ge=1, le=200_000)
    max_brief_tokens: int | None = Field(default=None, ge=1, le=100_000)


class InnerAgentProviderConfig(_StrictModel):
    """Provider-specific runtime settings selected by startup."""

    command: str = Field(min_length=1)
    working_directory: Literal["repo_root"] = "repo_root"
    allow_shellbrain_cli: bool = True


class InternalAgentsConfig(_StrictModel):
    """Typed internal-agent configuration loaded from YAML."""

    build_context: InnerAgentSettings
    build_knowledge: InnerAgentSettings
    providers: dict[InnerAgentProviderName, InnerAgentProviderConfig]

    @field_validator("providers")
    @classmethod
    def _validate_providers(
        cls,
        value: dict[InnerAgentProviderName, InnerAgentProviderConfig],
    ) -> dict[InnerAgentProviderName, InnerAgentProviderConfig]:
        """Require at least one configured provider."""

        if not value:
            raise ValueError("internal-agent providers must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_referenced_providers(self) -> "InternalAgentsConfig":
        """Require every configured agent to reference a known provider."""

        for agent_name in ("build_context", "build_knowledge"):
            agent = getattr(self, agent_name)
            if agent.provider not in self.providers:
                raise ValueError(
                    f"internal_agents.{agent_name}.provider is not configured"
                )
        return self
