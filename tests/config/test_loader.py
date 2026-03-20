"""Config loader contracts for renamed create and update policy sections."""

from pathlib import Path

from app.config.loader import YamlConfigProvider


def test_yaml_config_provider_exposes_separate_create_and_update_policy_sections() -> None:
    """yaml config provider should always expose separate create and update policy sections."""

    provider = YamlConfigProvider(Path("app/config/defaults"))

    assert provider.get_create_policy()["gates"] == ["schema", "semantic", "integrity"]
    assert provider.get_update_policy()["gates"] == ["schema", "semantic", "integrity"]
    assert provider.get_create_policy()["defaults"] == {"scope": "repo"}
    assert set(provider.get_create_policy()) == {"gates", "defaults"}
    assert set(provider.get_update_policy()) == {"gates"}
