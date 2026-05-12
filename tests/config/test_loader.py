"""Config loader contracts for renamed create and update policy sections."""

from pathlib import Path

import pytest

from app.core.entities.inner_agents import InternalAgentsConfig
from app.infrastructure.host_apps.inner_agents.codex_cli import CodexCliInnerAgentRunner
from app.startup.internal_agents import get_build_context_inner_agent_runner
from app.startup.settings import YamlConfigProvider


def test_yaml_config_provider_exposes_separate_create_and_update_policy_sections() -> (
    None
):
    """yaml config provider should always expose separate create and update policy sections."""

    provider = YamlConfigProvider(Path("app/settings/defaults"))

    assert provider.get_create_policy()["gates"] == ["schema", "semantic", "integrity"]
    assert provider.get_update_policy()["gates"] == ["schema", "semantic", "integrity"]
    assert provider.get_create_policy()["defaults"] == {"scope": "repo"}
    assert set(provider.get_create_policy()) == {"gates", "defaults"}
    assert set(provider.get_update_policy()) == {"gates"}


def test_yaml_config_provider_exposes_internal_agent_settings() -> None:
    """yaml config provider should expose per-agent model and reasoning settings."""

    provider = YamlConfigProvider(Path("app/settings/defaults"))
    settings = provider.get_internal_agents()

    assert settings["build_context"]["provider"] == "codex"
    assert settings["build_context"]["model"] == "gpt-5.4-mini"
    assert settings["build_context"]["reasoning"] == "low"
    assert "enabled" not in settings["build_context"]
    assert "fallback" not in settings["build_context"]
    assert "enabled" not in settings["build_knowledge"]
    assert "fallback" not in settings["build_knowledge"]
    assert settings["build_knowledge"]["model"] == "gpt-5.4"
    assert settings["providers"]["codex"]["command"] == "codex"
    assert settings["providers"]["codex"]["allow_shellbrain_cli"] is True


def test_internal_agent_config_rejects_removed_toggle_fields() -> None:
    """typed internal-agent config should reject stale enabled/fallback knobs."""

    provider = YamlConfigProvider(Path("app/settings/defaults"))
    settings = provider.get_internal_agents()
    settings["build_context"]["enabled"] = True
    settings["build_context"]["fallback"] = "deterministic"

    with pytest.raises(ValueError):
        InternalAgentsConfig.model_validate(settings)


def test_startup_still_wires_codex_build_context_runner() -> None:
    """startup should still compose the configured Codex build_context runner."""

    runner = get_build_context_inner_agent_runner()

    assert isinstance(runner, CodexCliInnerAgentRunner)
