"""Composition helpers for Shellbrain internal-agent providers."""

from __future__ import annotations

import shutil
from typing import Any

from pydantic import ValidationError

from app.core.entities.inner_agents import (
    BuildKnowledgeSettings,
    InnerAgentSettings,
    TeachKnowledgeSettings,
    WikiSummarySettings,
)
from app.core.ports.host_apps.inner_agents import (
    IBuildKnowledgeAgentRunner,
    IInnerAgentRunner,
    ITeachKnowledgeAgentRunner,
    IWikiSummaryAgentRunner,
)
from app.infrastructure.host_apps.inner_agents.claude_cli import ClaudeCliInnerAgentRunner
from app.infrastructure.host_apps.inner_agents.codex_cli import CodexCliInnerAgentRunner
from app.startup.config import get_config_provider
from app.startup.internal_agent_config import InternalAgentsConfig


_AUTO_PROVIDER = "auto"
_AUTO_PROVIDER_ORDER = ("codex", "claude")


def get_internal_agents_config() -> InternalAgentsConfig:
    """Return typed internal-agent settings from packaged YAML config."""

    raw_config = get_config_provider().get_internal_agents()
    try:
        return InternalAgentsConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise ValueError(f"Invalid internal-agent config: {exc}") from exc


def get_build_context_settings() -> InnerAgentSettings:
    """Return typed settings for the read-only build_context agent."""

    config = get_internal_agents_config()
    return _resolve_settings(config, config.build_context)


def get_build_knowledge_settings() -> BuildKnowledgeSettings:
    """Return typed settings for the build_knowledge agent."""

    config = get_internal_agents_config()
    return _resolve_settings(config, config.build_knowledge)


def get_teach_knowledge_settings() -> TeachKnowledgeSettings:
    """Return typed settings for the explicit teaching agent."""

    config = get_internal_agents_config()
    return _resolve_settings(config, config.teach)


def get_wiki_summary_settings() -> WikiSummarySettings:
    """Return typed settings for generated wiki summaries."""

    config = get_internal_agents_config()
    return _resolve_settings(config, config.wiki_summary)


def get_build_context_inner_agent_runner() -> IInnerAgentRunner | None:
    """Return the configured build_context provider adapter."""

    config = get_internal_agents_config()
    return _runner_for(config, config.build_context)


def get_build_knowledge_inner_agent_runner() -> IBuildKnowledgeAgentRunner | None:
    """Return the configured build_knowledge provider adapter."""

    config = get_internal_agents_config()
    return _runner_for(config, config.build_knowledge)


def get_teach_knowledge_inner_agent_runner() -> ITeachKnowledgeAgentRunner | None:
    """Return the configured explicit teaching provider adapter."""

    config = get_internal_agents_config()
    return _runner_for(config, config.teach)


def get_wiki_summary_inner_agent_runner() -> IWikiSummaryAgentRunner | None:
    """Return the configured wiki_summary provider adapter."""

    config = get_internal_agents_config()
    return _runner_for(config, config.wiki_summary)


def get_internal_agents_settings() -> dict[str, Any]:
    """Return normalized internal-agent settings for diagnostics and tests."""

    return get_internal_agents_config().model_dump(mode="python")


def _runner_for(
    config: InternalAgentsConfig,
    settings: Any,
) -> (
    IInnerAgentRunner
    | IBuildKnowledgeAgentRunner
    | ITeachKnowledgeAgentRunner
    | IWikiSummaryAgentRunner
    | None
):
    provider_name = _select_provider(config, settings.provider)
    if provider_name is None:
        return None
    provider = config.providers[provider_name]
    if provider_name == "codex":
        return CodexCliInnerAgentRunner(command=provider.command)
    if provider_name == "claude":
        return ClaudeCliInnerAgentRunner(command=provider.command)
    return None


def _resolve_settings(
    config: InternalAgentsConfig,
    settings: Any,
):
    provider_name = _select_provider(config, settings.provider)
    if provider_name is None:
        return settings
    provider = config.providers[provider_name]
    return settings.model_copy(
        update={
            "provider": provider_name,
            "model": provider.model,
        }
    )


def _select_provider(
    config: InternalAgentsConfig,
    requested_provider: str,
) -> str | None:
    if requested_provider != _AUTO_PROVIDER:
        return requested_provider
    for provider_name in _AUTO_PROVIDER_ORDER:
        provider = config.providers.get(provider_name)
        if provider is not None and shutil.which(provider.command) is not None:
            return provider_name
    return None
