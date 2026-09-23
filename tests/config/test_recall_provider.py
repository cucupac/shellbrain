"""Verify persisted provider selection and dependency isolation."""

import pytest

from app.entrypoints.cli.main import main
from app.infrastructure.local_state.recall_provider_store import (
    load_recall_provider,
    save_recall_provider,
)
from app.infrastructure.host_apps.inner_agents.inception_api import (
    InceptionApiInnerAgentRunner,
)
from app.startup.internal_agents import (
    get_build_context_inner_agent_runner,
    get_build_knowledge_settings,
)


@pytest.fixture(autouse=True)
def home(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELLBRAIN_HOME", str(tmp_path))
    monkeypatch.delenv("INCEPTION_API_KEY", raising=False)
    return tmp_path


@pytest.mark.parametrize("provider", ["codex", "claude", "inception"])
def test_selection_without_services(provider, home, capsys):
    assert load_recall_provider() == "codex"
    assert main(["admin", "recall", "provider", provider]) == 0
    assert load_recall_provider() == provider
    assert f"Recall provider: {provider}" in capsys.readouterr().out
    assert (home / "recall-provider.toml").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "text",
    ['provider="auto"', 'provider=["codex"]', "broken=", 'provider="codex"\nextra=1'],
)
def test_bad_configuration_fails(home, text):
    (home / "recall-provider.toml").write_text(text)
    with pytest.raises(ValueError):
        load_recall_provider()


def test_failed_replace_preserves_previous_selection(monkeypatch):
    save_recall_provider("claude")

    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr(
        "app.infrastructure.local_state.recall_provider_store.os.replace", fail
    )
    with pytest.raises(OSError):
        save_recall_provider("inception")
    assert load_recall_provider() == "claude"


def test_missing_key_does_not_break_shared_dependencies(monkeypatch):
    save_recall_provider("inception")
    from app.startup.operation_dependencies import build_operation_dependencies

    dependencies = build_operation_dependencies()
    assert dependencies.build_context_inner_agent_runner is None
    assert dependencies.shadow_git_store is not None
    settings = dependencies.build_context_settings
    assert settings.model == "mercury-2.5" and settings.timeout_seconds == 10
    assert settings.reasoning == "instant"
    monkeypatch.setenv("INCEPTION_API_KEY", "test-key")
    assert isinstance(
        get_build_context_inner_agent_runner(settings), InceptionApiInnerAgentRunner
    )
    assert get_build_knowledge_settings().provider != "inception"


@pytest.mark.parametrize(
    "args",
    [
        ["init"],
        ["teach"],
        ["admin", "doctor"],
        ["admin", "migrate"],
        ["admin", "analytics"],
        ["admin", "backfill-token-usage"],
        ["admin", "session-state"],
        ["admin", "recall", "fast"],
        ["admin", "recall", "full"],
        ["admin", "recall", "status"],
        ["admin", "recall", "provider"],
        ["admin", "recall", "provider", "auto"],
    ],
)
def test_removed_commands_are_rejected(args):
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2


@pytest.mark.parametrize("value", ["test-key", '"test-key"', "'test-key' # comment"])
def test_saved_key_is_loaded_without_host_environment(home, value):
    from app.infrastructure.local_state.recall_credentials import load_inception_api_key
    from app.startup.internal_agents import get_build_context_settings

    (home / ".env").write_text(f"# Credentials\nINCEPTION_API_KEY={value}\n")
    save_recall_provider("inception")
    assert load_inception_api_key() == "test-key"
    assert isinstance(
        get_build_context_inner_agent_runner(get_build_context_settings()),
        InceptionApiInnerAgentRunner,
    )
    (home / ".env").write_text("INCEPTION_API_KEY=replacement-key\n")
    assert load_inception_api_key() == "replacement-key"


def test_environment_overrides_saved_key(home, monkeypatch):
    from app.infrastructure.local_state.recall_credentials import load_inception_api_key

    (home / ".env").write_text("INCEPTION_API_KEY=file-key\n")
    monkeypatch.setenv("INCEPTION_API_KEY", "environment-key")
    assert load_inception_api_key() == "environment-key"


def test_key_lookup_ignores_repository_and_does_not_execute_file(home, tmp_path, monkeypatch):
    from app.infrastructure.local_state.recall_credentials import load_inception_api_key

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("INCEPTION_API_KEY=repo-key\n")
    monkeypatch.chdir(repo)
    marker = home / "executed"
    (home / ".env").write_text(f"touch {marker}\nOTHER_KEY=unused\n")
    assert load_inception_api_key() == ""
    assert not marker.exists()


def test_invalid_key_does_not_expose_secret(home):
    from app.infrastructure.local_state.recall_credentials import load_inception_api_key

    (home / ".env").write_text('INCEPTION_API_KEY="secret-value\n')
    with pytest.raises(ValueError) as error:
        load_inception_api_key()
    assert "secret-value" not in str(error.value)
