"""Runtime-config usage contracts for boot helpers."""

from pathlib import Path

from shellbrain.boot.db import get_db_dsn
from shellbrain.config.loader import YamlConfigProvider


def test_db_boot_should_always_resolve_the_runtime_configured_dsn_env(monkeypatch) -> None:
    """db boot should always resolve the runtime-configured dsn env."""

    class _FakeProvider:
        """Stub config provider for runtime database settings."""

        def get_runtime(self) -> dict[str, object]:
            return {"database": {"dsn_env": "CUSTOM_MEMORY_DSN"}}

    monkeypatch.setattr("shellbrain.boot.db.get_config_provider", lambda: _FakeProvider())
    monkeypatch.setenv("CUSTOM_MEMORY_DSN", "postgresql://configured-dsn")

    assert get_db_dsn() == "postgresql://configured-dsn"


def test_runtime_yaml_should_always_define_database_cli_and_embedding_sections() -> None:
    """runtime yaml should always define database cli and embedding sections."""

    provider = YamlConfigProvider(Path("shellbrain/config/defaults"))
    runtime = provider.get_runtime()

    assert runtime["database"] == {"dsn_env": "SHELLBRAIN_DB_DSN"}
    assert runtime["cli"] == {"default_mode": "targeted", "include_global": True}
    assert runtime["embeddings"] == {
        "provider": "sentence_transformers",
        "model": "all-MiniLM-L6-v2",
    }
