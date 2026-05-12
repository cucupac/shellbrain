"""Composition helpers for Shellbrain internal-agent providers."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.core.entities.inner_agents import (
    InnerAgentSettings,
    InternalAgentsConfig,
)
from app.core.ports.host_apps.inner_agents import IInnerAgentRunner
from app.infrastructure.host_apps.inner_agents.codex_cli import CodexCliInnerAgentRunner
from app.startup.config import get_config_provider


def get_internal_agents_config() -> InternalAgentsConfig:
    """Return typed internal-agent settings from packaged YAML config."""

    raw_config = get_config_provider().get_internal_agents()
    try:
        return InternalAgentsConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise ValueError(f"Invalid internal-agent config: {exc}") from exc


def get_build_context_settings() -> InnerAgentSettings:
    """Return typed settings for the read-only build_context agent."""

    return get_internal_agents_config().build_context


def get_build_context_inner_agent_runner() -> IInnerAgentRunner | None:
    """Return the configured build_context provider adapter."""

    config = get_internal_agents_config()
    settings = config.build_context
    provider = config.providers.get(settings.provider)
    if provider is None:
        return None
    if settings.provider == "codex":
        return CodexCliInnerAgentRunner(
            command=provider.command,
            working_directory=provider.working_directory,
            allow_shellbrain_cli=provider.allow_shellbrain_cli,
        )
    return None


def get_internal_agents_settings() -> dict[str, Any]:
    """Return normalized internal-agent settings for diagnostics and tests."""

    return get_internal_agents_config().model_dump(mode="python")
