"""Runtime-config usage contracts for boot helpers."""

from pathlib import Path

from app.boot.admin_db import should_fail_on_unsafe_app_role
from app.boot.db import get_db_dsn
from app.config.loader import YamlConfigProvider
from app.periphery.admin.machine_state import (
    BackupState,
    DatabaseState,
    EmbeddingRuntimeState,
    MachineConfig,
    ManagedInstanceState,
)


def test_db_boot_should_always_resolve_the_runtime_configured_dsn_env(monkeypatch) -> None:
    """db boot should always resolve the runtime-configured dsn env."""

    class _FakeProvider:
        """Stub config provider for runtime database settings."""

        def get_runtime(self) -> dict[str, object]:
            return {"database": {"dsn_env": "CUSTOM_MEMORY_DSN", "admin_dsn_env": "CUSTOM_ADMIN_DSN"}}

    monkeypatch.setattr("app.boot.db.get_config_provider", lambda: _FakeProvider())
    monkeypatch.setattr("app.boot.db.try_load_machine_config", lambda: (None, None))
    monkeypatch.setenv("CUSTOM_MEMORY_DSN", "postgresql://configured-dsn")

    assert get_db_dsn() == "postgresql://configured-dsn"


def test_db_boot_should_prefer_machine_config_over_legacy_env(monkeypatch) -> None:
    """db boot should use the managed machine config before env-based runtime settings."""

    machine_config = MachineConfig(
        config_version=1,
        bootstrap_version=1,
        runtime_mode="managed_local",
        bootstrap_state="ready",
        current_step=None,
        last_error=None,
        database=DatabaseState(
            app_dsn="postgresql+psycopg://machine-app@localhost:55432/shellbrain",
            admin_dsn="postgresql+psycopg://machine-admin@localhost:55432/shellbrain",
        ),
        managed=ManagedInstanceState(
            instance_id="inst-1",
            container_name="shellbrain-postgres",
            image="pgvector/pgvector:pg16",
            host="127.0.0.1",
            port=55432,
            db_name="shellbrain",
            data_dir="/tmp/shellbrain-data",
            admin_user="shellbrain_admin",
            admin_password="admin-secret",
            app_user="shellbrain_app",
            app_password="app-secret",
        ),
        backups=BackupState(root="/tmp/shellbrain-backups"),
        embeddings=EmbeddingRuntimeState(
            provider="sentence_transformers",
            model="all-MiniLM-L6-v2",
            model_revision=None,
            backend_version="1.0.0",
            cache_path="/tmp/shellbrain-models",
            readiness_state="ready",
            last_error=None,
        ),
    )

    monkeypatch.setattr("app.boot.db.try_load_machine_config", lambda: (machine_config, None))
    monkeypatch.setenv("SHELLBRAIN_DB_DSN", "postgresql://legacy-env")

    assert get_db_dsn() == "postgresql+psycopg://machine-app@localhost:55432/shellbrain"


def test_db_boot_should_fail_cleanly_when_machine_config_is_corrupt(monkeypatch) -> None:
    """db boot should direct the user to rerun init when machine config is corrupt."""

    monkeypatch.setattr("app.boot.db.try_load_machine_config", lambda: (None, "corrupt toml"))

    try:
        get_db_dsn()
    except RuntimeError as exc:
        assert "rerun `shellbrain init`" in str(exc).lower()
    else:  # pragma: no cover - defensive guard
        raise AssertionError("Expected get_db_dsn() to fail when machine config is corrupt.")


def test_runtime_yaml_should_always_define_database_cli_and_embedding_sections() -> None:
    """runtime yaml should always define database cli and embedding sections."""

    provider = YamlConfigProvider(Path("app/config/defaults"))
    runtime = provider.get_runtime()

    assert runtime["database"] == {
        "dsn_env": "SHELLBRAIN_DB_DSN",
        "admin_dsn_env": "SHELLBRAIN_DB_ADMIN_DSN",
    }
    assert runtime["cli"] == {"default_mode": "targeted", "include_global": True}
    assert runtime["embeddings"] == {
        "provider": "sentence_transformers",
        "model": "all-MiniLM-L6-v2",
    }


def test_unsafe_app_role_should_fail_closed_by_default(monkeypatch) -> None:
    """Unsafe app-role checks should fail closed unless explicitly relaxed."""

    monkeypatch.delenv("SHELLBRAIN_FAIL_ON_UNSAFE_DB_ROLE", raising=False)

    assert should_fail_on_unsafe_app_role() is True


def test_unsafe_app_role_can_be_explicitly_relaxed(monkeypatch) -> None:
    """Unsafe app-role checks may be downgraded explicitly for controlled debugging."""

    monkeypatch.setenv("SHELLBRAIN_FAIL_ON_UNSAFE_DB_ROLE", "false")

    assert should_fail_on_unsafe_app_role() is False
