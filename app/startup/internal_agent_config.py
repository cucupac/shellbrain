"""Startup-owned config models for internal-agent composition."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.entities.inner_agents import (
    BuildContextSettings,
    BuildKnowledgeSettings,
    InnerAgentProviderName,
    TeachKnowledgeSettings,
    WikiSummarySettings,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InnerAgentProviderConfig(_StrictModel):
    """Provider-specific runtime settings selected by startup."""

    command: str = Field(min_length=1)
    model: str = Field(min_length=1)


class InternalAgentsConfig(_StrictModel):
    """Typed internal-agent configuration loaded from YAML."""

    build_context: BuildContextSettings
    build_knowledge: BuildKnowledgeSettings
    teach: TeachKnowledgeSettings
    wiki_summary: WikiSummarySettings
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

        for agent_name in ("build_context", "build_knowledge", "teach", "wiki_summary"):
            agent = getattr(self, agent_name)
            if agent.provider == "auto":
                continue
            if agent.provider not in self.providers:
                raise ValueError(
                    f"internal_agents.{agent_name}.provider is not configured"
                )
        return self
