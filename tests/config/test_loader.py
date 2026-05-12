"""Config loader contracts for renamed create and update policy sections."""

from pathlib import Path

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
    assert settings["build_knowledge"]["model"] == "gpt-5.4"
    assert settings["providers"]["codex"]["command"] == "codex"
