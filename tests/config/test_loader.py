"""Config loader contracts for renamed create and update policy sections."""

from pathlib import Path

import pytest

import app.core.entities.inner_agents as core_inner_agents
from app.infrastructure.host_apps.inner_agents.codex_cli import CodexCliInnerAgentRunner
from app.startup.internal_agent_config import InternalAgentsConfig
from app.startup.internal_agents import (
    get_build_context_inner_agent_runner,
    get_build_context_settings,
    get_build_knowledge_inner_agent_runner,
    get_build_knowledge_settings,
)
from app.startup.internal_agent_config import default_internal_agents_config


@pytest.fixture(autouse=True)
def _isolated_shellbrain_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SHELLBRAIN_HOME", str(tmp_path / "shellbrain-home"))


def test_packaged_defaults_preserve_inner_agent_settings() -> None:
    """Packaged defaults should expose per-agent model and reasoning settings."""

    settings = default_internal_agents_config().model_dump()

    assert settings["build_context"]["provider"] == "codex"
    assert settings["build_context"]["model"] == "gpt-5.6-luna"
    assert settings["build_context"]["reasoning"] == "low"
    assert settings["build_context"]["max_brief_tokens"] == 500
    assert "enabled" not in settings["build_context"]
    assert "fallback" not in settings["build_context"]
    assert "enabled" not in settings["build_knowledge"]
    assert "fallback" not in settings["build_knowledge"]
    assert settings["build_knowledge"]["model"] == "gpt-5.6-luna"
    assert settings["build_knowledge"]["reasoning"] == "xhigh"
    assert settings["build_knowledge"]["timeout_seconds"] == 600
    assert settings["build_knowledge"]["max_shellbrain_reads"] == 8
    assert settings["build_knowledge"]["max_code_files"] == 24
    assert settings["build_knowledge"]["max_write_commands"] == 20
    assert settings["build_knowledge"]["idle_stable_seconds"] == 900
    assert settings["build_knowledge"]["running_run_stale_seconds"] == 3600
    assert "max_private_reads" not in settings["build_knowledge"]
    assert settings["providers"]["codex"]["command"] == "codex"
    assert settings["providers"]["codex"]["model_override"] is None
    assert settings["providers"]["claude"]["command"] == "claude"
    assert settings["providers"]["claude"]["model_override"] == "sonnet"
    assert "working_directory" not in settings["providers"]["codex"]
    assert "allow_shellbrain_cli" not in settings["providers"]["codex"]


def test_internal_agent_config_rejects_removed_toggle_fields() -> None:
    """typed internal-agent config should reject stale enabled/fallback knobs."""

    settings = default_internal_agents_config().model_dump()
    settings["build_context"]["enabled"] = True
    settings["build_context"]["fallback"] = "deterministic"

    with pytest.raises(ValueError):
        InternalAgentsConfig.model_validate(settings)


def test_internal_agent_config_rejects_removed_candidate_token_budget() -> None:
    """typed build_context config should reject stale synthesis-token ceilings."""

    settings = default_internal_agents_config().model_dump()
    settings["build_context"]["max_candidate_tokens"] = 10_000

    with pytest.raises(ValueError):
        InternalAgentsConfig.model_validate(settings)


def test_internal_agent_config_rejects_removed_provider_fields() -> None:
    """typed provider config should reject stale runtime knobs."""

    settings = default_internal_agents_config().model_dump()
    settings["providers"]["codex"]["working_directory"] = "repo_root"
    settings["providers"]["codex"]["allow_shellbrain_cli"] = True

    with pytest.raises(ValueError):
        InternalAgentsConfig.model_validate(settings)


def test_provider_runtime_config_is_startup_owned() -> None:
    """provider command settings should stay out of core domain entities."""

    assert not hasattr(core_inner_agents, "InnerAgentProviderConfig")
    assert not hasattr(core_inner_agents, "InternalAgentsConfig")


def test_internal_agent_config_accepts_auto_without_auto_provider() -> None:
    """auto is a startup selector, not a configured provider key."""

    settings = default_internal_agents_config().model_dump()

    InternalAgentsConfig.model_validate(settings)


def test_internal_agent_config_rejects_unknown_explicit_provider() -> None:
    """unknown explicit providers should still fail validation."""

    settings = default_internal_agents_config().model_dump()
    settings["build_context"]["provider"] = "unknown"

    with pytest.raises(ValueError):
        InternalAgentsConfig.model_validate(settings)


def test_internal_agent_config_requires_non_codex_model_override() -> None:
    """Providers with fixed models should declare their override."""

    settings = default_internal_agents_config().model_dump()
    del settings["providers"]["claude"]["model_override"]

    with pytest.raises(ValueError):
        InternalAgentsConfig.model_validate(settings)


def test_startup_auto_prefers_codex_when_both_commands_exist(monkeypatch) -> None:
    """auto should prefer Codex over Claude when both CLIs are installed."""

    _patch_which(monkeypatch, {"codex", "claude"})

    runner = get_build_context_inner_agent_runner(get_build_context_settings())

    assert isinstance(runner, CodexCliInnerAgentRunner)


def test_explicit_provider_does_not_auto_fallback(monkeypatch) -> None:
    """explicit provider selection should construct that runner without probing fallback."""

    settings = default_internal_agents_config().model_dump()
    settings["build_context"]["provider"] = "codex"
    monkeypatch.setattr(
        "app.startup.internal_agents.get_internal_agents_config",
        lambda: InternalAgentsConfig.model_validate(settings),
    )
    _patch_which(monkeypatch, {"claude"})

    runner = get_build_context_inner_agent_runner(get_build_context_settings())
    resolved = get_build_context_settings()

    assert isinstance(runner, CodexCliInnerAgentRunner)
    assert resolved.provider == "codex"
    assert resolved.model == "gpt-5.6-luna"


@pytest.mark.parametrize(
    "runner_getter",
    (get_build_knowledge_inner_agent_runner,),
)
def test_startup_wires_codex_non_recall_runners(monkeypatch, runner_getter) -> None:
    """startup should compose the configured non-recall runners."""

    _patch_which(monkeypatch, {"codex", "claude"})

    runner = runner_getter()

    assert isinstance(runner, CodexCliInnerAgentRunner)


@pytest.mark.parametrize(
    ("settings_getter", "expected_model"),
    ((get_build_knowledge_settings, "gpt-5.6-luna"),),
)
def test_startup_preserves_codex_workflow_models(
    monkeypatch, settings_getter, expected_model: str
) -> None:
    """Codex workflows should use their configured models."""

    _patch_which(monkeypatch, {"codex", "claude"})

    settings = settings_getter()

    assert settings.provider == "codex"
    assert settings.model == expected_model


def _patch_which(monkeypatch, installed: set[str]) -> None:
    def _fake_which(command: str) -> str | None:
        return f"/usr/bin/{command}" if command in installed else None

    monkeypatch.setattr("app.startup.internal_agents.shutil.which", _fake_which)
