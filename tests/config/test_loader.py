"""Config loader contracts for renamed create and update policy sections."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import app.core.entities.inner_agents as core_inner_agents
from app.infrastructure.host_apps.inner_agents.claude_cli import ClaudeCliInnerAgentRunner
from app.infrastructure.host_apps.inner_agents.codex_cli import CodexCliInnerAgentRunner
from app.infrastructure.local_state.recall_mode_store import (
    load_recall_mode,
    save_recall_mode,
)
from app.startup.internal_agent_config import InternalAgentsConfig
from app.startup.internal_agents import (
    get_build_context_inner_agent_runner,
    get_build_context_settings,
    get_build_knowledge_inner_agent_runner,
    get_teach_knowledge_inner_agent_runner,
    get_wiki_summary_inner_agent_runner,
)
from app.startup.settings import YamlConfigProvider


@pytest.fixture(autouse=True)
def _isolated_shellbrain_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SHELLBRAIN_HOME", str(tmp_path / "shellbrain-home"))


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

    assert settings["build_context"]["strategy"] == "deterministic_synthesis"
    assert settings["build_context"]["provider"] == "auto"
    assert settings["build_context"]["model"] == "gpt-5.4-mini"
    assert settings["build_context"]["reasoning"] == "low"
    assert "enabled" not in settings["build_context"]
    assert "fallback" not in settings["build_context"]
    assert "enabled" not in settings["build_knowledge"]
    assert "fallback" not in settings["build_knowledge"]
    assert settings["build_knowledge"]["model"] == "gpt-5.4-mini"
    assert settings["build_knowledge"]["reasoning"] == "xhigh"
    assert settings["build_knowledge"]["timeout_seconds"] == 600
    assert settings["build_knowledge"]["max_shellbrain_reads"] == 8
    assert settings["build_knowledge"]["max_code_files"] == 24
    assert settings["build_knowledge"]["max_write_commands"] == 20
    assert settings["build_knowledge"]["idle_stable_seconds"] == 900
    assert settings["build_knowledge"]["running_run_stale_seconds"] == 3600
    assert "max_private_reads" not in settings["build_knowledge"]
    assert settings["teach"]["model"] == "gpt-5.4-mini"
    assert settings["teach"]["reasoning"] == "medium"
    assert settings["teach"]["timeout_seconds"] == 600
    assert settings["teach"]["max_shellbrain_reads"] == 6
    assert settings["teach"]["max_code_files"] == 5
    assert settings["teach"]["max_write_commands"] == 12
    assert "idle_stable_seconds" not in settings["teach"]
    assert settings["wiki_summary"]["model"] == "gpt-5.4-mini"
    assert settings["wiki_summary"]["reasoning"] == "medium"
    assert settings["wiki_summary"]["timeout_seconds"] == 120
    assert settings["wiki_summary"]["prompt_version"] == "wiki-summary.v1"
    assert settings["wiki_summary"]["startup_batch_limit"] == 20
    assert settings["wiki_summary"]["periodic_batch_limit"] == 5
    assert settings["providers"]["codex"]["command"] == "codex"
    assert settings["providers"]["codex"]["model"] == "gpt-5.4-mini"
    assert settings["providers"]["claude"]["command"] == "claude"
    assert settings["providers"]["claude"]["model"] == "sonnet"
    assert "working_directory" not in settings["providers"]["codex"]
    assert "allow_shellbrain_cli" not in settings["providers"]["codex"]


def test_internal_agent_config_rejects_removed_toggle_fields() -> None:
    """typed internal-agent config should reject stale enabled/fallback knobs."""

    provider = YamlConfigProvider(Path("app/settings/defaults"))
    settings = provider.get_internal_agents()
    settings["build_context"]["enabled"] = True
    settings["build_context"]["fallback"] = "deterministic"

    with pytest.raises(ValueError):
        InternalAgentsConfig.model_validate(settings)


def test_internal_agent_config_rejects_removed_candidate_token_budget() -> None:
    """typed build_context config should reject stale synthesis-token ceilings."""

    provider = YamlConfigProvider(Path("app/settings/defaults"))
    settings = provider.get_internal_agents()
    settings["build_context"]["max_candidate_tokens"] = 10_000

    with pytest.raises(ValueError):
        InternalAgentsConfig.model_validate(settings)


def test_internal_agent_config_rejects_removed_provider_fields() -> None:
    """typed provider config should reject stale runtime knobs."""

    provider = YamlConfigProvider(Path("app/settings/defaults"))
    settings = provider.get_internal_agents()
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

    provider = YamlConfigProvider(Path("app/settings/defaults"))
    settings = provider.get_internal_agents()

    InternalAgentsConfig.model_validate(settings)


def test_internal_agent_config_rejects_unknown_explicit_provider() -> None:
    """unknown explicit providers should still fail validation."""

    provider = YamlConfigProvider(Path("app/settings/defaults"))
    settings = provider.get_internal_agents()
    settings["build_context"]["provider"] = "unknown"

    with pytest.raises(ValueError):
        InternalAgentsConfig.model_validate(settings)


def test_internal_agent_config_requires_provider_model() -> None:
    """provider models should be explicit, not inferred from agent defaults."""

    provider = YamlConfigProvider(Path("app/settings/defaults"))
    settings = provider.get_internal_agents()
    del settings["providers"]["claude"]["model"]

    with pytest.raises(ValueError):
        InternalAgentsConfig.model_validate(settings)


def test_startup_auto_prefers_codex_when_both_commands_exist(monkeypatch) -> None:
    """auto should prefer Codex over Claude when both CLIs are installed."""

    _patch_which(monkeypatch, {"codex", "claude"})

    runner = get_build_context_inner_agent_runner()

    assert isinstance(runner, CodexCliInnerAgentRunner)


def test_startup_auto_uses_claude_when_codex_is_missing(monkeypatch) -> None:
    """auto should use Claude only when Codex is unavailable."""

    _patch_which(monkeypatch, {"claude"})

    runner = get_build_context_inner_agent_runner()

    assert isinstance(runner, ClaudeCliInnerAgentRunner)


def test_startup_auto_returns_no_runner_when_no_provider_is_installed(monkeypatch) -> None:
    """auto should not construct a runner when no configured CLI exists."""

    _patch_which(monkeypatch, set())

    assert get_build_context_inner_agent_runner() is None


def test_startup_resolves_runtime_settings_to_selected_provider(monkeypatch) -> None:
    """runtime settings should not pass provider=auto into provider requests."""

    _patch_which(monkeypatch, {"claude"})

    settings = get_build_context_settings()

    assert settings.provider == "claude"
    assert settings.model == "sonnet"


def test_recall_mode_store_defaults_to_full_when_missing(tmp_path: Path) -> None:
    """missing recall override should preserve packaged defaults."""

    mode, path, exists = load_recall_mode(tmp_path / "missing.toml")

    assert mode == "full"
    assert path == tmp_path / "missing.toml"
    assert exists is False


@pytest.mark.parametrize("mode", ("fast", "full"))
def test_recall_mode_store_round_trips_modes(tmp_path: Path, mode: str) -> None:
    """machine-local recall mode should persist as tiny TOML."""

    path = tmp_path / "recall.toml"

    save_recall_mode(mode, path)

    assert path.read_text(encoding="utf-8") == f'mode = "{mode}"\n'
    assert load_recall_mode(path) == (mode, path, True)


@pytest.mark.parametrize(
    "text",
    ("mode = [", 'mode = "turbo"\n', 'mode = "fast"\nextra = true\n'),
)
def test_recall_mode_store_rejects_invalid_config(tmp_path: Path, text: str) -> None:
    """bad recall override files should fail clearly."""

    path = tmp_path / "recall.toml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid recall mode config"):
        load_recall_mode(path)


def test_recall_mode_fast_skips_build_context_runner(monkeypatch, tmp_path: Path) -> None:
    """fast recall mode should force deterministic-only recall."""

    monkeypatch.setenv("SHELLBRAIN_HOME", str(tmp_path))
    save_recall_mode("fast")
    _patch_which(monkeypatch, {"codex", "claude"})

    settings = get_build_context_settings()

    assert settings.strategy == "deterministic_only"
    assert get_build_context_inner_agent_runner() is None


def test_recall_mode_full_forces_synthesis(monkeypatch, tmp_path: Path) -> None:
    """full recall mode should force the normal synthesis strategy."""

    provider = YamlConfigProvider(Path("app/settings/defaults"))
    settings = provider.get_internal_agents()
    settings["build_context"]["strategy"] = "deterministic_only"
    monkeypatch.setattr(
        "app.startup.internal_agents.get_config_provider",
        lambda: SimpleNamespace(get_internal_agents=lambda: settings),
    )
    monkeypatch.setenv("SHELLBRAIN_HOME", str(tmp_path))
    save_recall_mode("full")
    _patch_which(monkeypatch, {"codex"})

    resolved = get_build_context_settings()

    assert resolved.strategy == "deterministic_synthesis"
    assert isinstance(get_build_context_inner_agent_runner(), CodexCliInnerAgentRunner)


def test_missing_recall_mode_preserves_packaged_strategy(
    monkeypatch, tmp_path: Path
) -> None:
    """missing recall override should not rewrite packaged build-context config."""

    monkeypatch.setenv("SHELLBRAIN_HOME", str(tmp_path))

    settings = get_build_context_settings()

    assert settings.strategy == "deterministic_synthesis"


def test_explicit_provider_does_not_auto_fallback(monkeypatch) -> None:
    """explicit provider selection should construct that runner without probing fallback."""

    provider = YamlConfigProvider(Path("app/settings/defaults"))
    settings = provider.get_internal_agents()
    settings["build_context"]["provider"] = "codex"
    monkeypatch.setattr(
        "app.startup.internal_agents.get_config_provider",
        lambda: SimpleNamespace(get_internal_agents=lambda: settings),
    )
    _patch_which(monkeypatch, {"claude"})

    runner = get_build_context_inner_agent_runner()
    resolved = get_build_context_settings()

    assert isinstance(runner, CodexCliInnerAgentRunner)
    assert resolved.provider == "codex"
    assert resolved.model == "gpt-5.4-mini"


@pytest.mark.parametrize(
    "runner_getter",
    (
        get_build_knowledge_inner_agent_runner,
        get_teach_knowledge_inner_agent_runner,
        get_wiki_summary_inner_agent_runner,
    ),
)
def test_startup_wires_codex_non_recall_runners(monkeypatch, runner_getter) -> None:
    """startup should compose the configured non-recall runners."""

    _patch_which(monkeypatch, {"codex", "claude"})

    runner = runner_getter()

    assert isinstance(runner, CodexCliInnerAgentRunner)


def _patch_which(monkeypatch, installed: set[str]) -> None:
    def _fake_which(command: str) -> str | None:
        return f"/usr/bin/{command}" if command in installed else None

    monkeypatch.setattr("app.startup.internal_agents.shutil.which", _fake_which)
