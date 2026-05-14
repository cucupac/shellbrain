"""Startup-owned config models for internal-agent composition."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.entities.inner_agents import (
    BuildContextSettings,
    BuildKnowledgeSettings,
    InnerAgentProviderName,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InnerAgentProviderConfig(_StrictModel):
    """Provider-specific runtime settings selected by startup."""

    command: str = Field(min_length=1)
    working_directory: Literal["repo_root"] = "repo_root"
    allow_shellbrain_cli: bool = True


class InternalAgentsConfig(_StrictModel):
    """Typed internal-agent configuration loaded from YAML."""

    build_context: BuildContextSettings
    build_knowledge: BuildKnowledgeSettings
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
