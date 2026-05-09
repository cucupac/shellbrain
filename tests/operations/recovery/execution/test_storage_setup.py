"""Storage-selection contracts for guided init bootstrap."""

from __future__ import annotations

import pytest

from app.infrastructure.postgres_admin import storage_setup
from app.core.entities.admin_errors import InitConflictError, InitDependencyError
from app.infrastructure.local_state.machine_config_store import (
    BackupState,
    DatabaseState,
    EmbeddingRuntimeState,
    MachineConfig,
    ManagedInstanceState,
)


def test_resolve_storage_selection_should_prompt_for_first_run_managed_default(
    monkeypatch,
) -> None:
    """first bootstrap should default to managed-local when the user presses enter."""

    reader = _FakeTerminal(["\n"])
    writer = _FakeTerminal([], is_tty=True)
    monkeypatch.setattr(
        storage_setup, "_open_interactive_stream", lambda: (reader, writer, writer)
    )
    monkeypatch.setattr(storage_setup, "_close_interactive_stream", lambda stream: None)

    selection = storage_setup.resolve_storage_selection(
        existing_config=None,
        storage_flag=None,
        admin_dsn_flag=None,
    )

    assert selection.runtime_mode == "managed_local"
    assert selection.admin_dsn is None


def test_resolve_storage_selection_should_use_dev_tty_fallback_for_external_prompt(
    monkeypatch,
) -> None:
    """pipe installs should still prompt through /dev/tty when stdin is not interactive."""

    handle = _FakeTerminal(
        ["2\n", "postgresql+psycopg://admin:secret@db.example.com:5432/shellbrain\n"]
    )
    writer = _FakeTerminal([], is_tty=True)
    open_modes: list[str] = []
    monkeypatch.setattr(storage_setup.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(storage_setup.sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(storage_setup.sys, "stderr", writer)
    monkeypatch.setattr(
        storage_setup.Path,
        "open",
        lambda self, mode="r", *args, **kwargs: open_modes.append(mode) or handle,
    )

    selection = storage_setup.resolve_storage_selection(
        existing_config=None,
        storage_flag=None,
        admin_dsn_flag=None,
    )

    assert selection.runtime_mode == "external_postgres"
    assert (
        selection.admin_dsn
        == "postgresql+psycopg://admin:secret@db.example.com:5432/shellbrain"
    )
    assert open_modes == ["r", "r"]
    assert "Choose 1 or 2 [1]: " in "".join(writer.output)


def test_resolve_storage_selection_should_fail_cleanly_without_any_interactive_stream(
    monkeypatch,
) -> None:
    """non-interactive first bootstrap should raise a stable guidance error."""

    monkeypatch.setattr(storage_setup.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(storage_setup.sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(
        storage_setup.Path,
        "open",
        lambda self, *args, **kwargs: (_ for _ in ()).throw(OSError("no tty")),
    )

    with pytest.raises(InitDependencyError) as excinfo:
        storage_setup.resolve_storage_selection(
            existing_config=None,
            storage_flag=None,
            admin_dsn_flag=None,
        )

    assert "--storage managed" in str(excinfo.value)
    assert "--storage external --admin-dsn <dsn>" in str(excinfo.value)


def test_resolve_storage_selection_should_fail_cleanly_without_any_visible_output_stream(
    monkeypatch,
) -> None:
    """first bootstrap should fail when prompt input exists but no visible writer does."""

    handle = _FakeTerminal(["1\n"])
    monkeypatch.setattr(storage_setup.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(storage_setup.sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(storage_setup.sys.stderr, "isatty", lambda: False)
    monkeypatch.setattr(
        storage_setup.Path, "open", lambda self, *args, **kwargs: handle
    )

    with pytest.raises(InitDependencyError) as excinfo:
        storage_setup.resolve_storage_selection(
            existing_config=None,
            storage_flag=None,
            admin_dsn_flag=None,
        )

    assert "--storage managed" in str(excinfo.value)
    assert "--storage external --admin-dsn <dsn>" in str(excinfo.value)


def test_resolve_storage_selection_should_bypass_prompt_when_existing_config_exists(
    monkeypatch,
) -> None:
    """existing machine config should make init non-interactive by default."""

    monkeypatch.setattr(
        storage_setup,
        "_prompt_for_storage_mode",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected prompt")),
    )

    selection = storage_setup.resolve_storage_selection(
        existing_config=_managed_machine_config(),
        storage_flag=None,
        admin_dsn_flag=None,
    )

    assert selection.runtime_mode == "managed_local"
    assert (
        selection.admin_dsn == "postgresql+psycopg://admin@127.0.0.1:55432/shellbrain"
    )


def test_resolve_storage_selection_should_bypass_prompt_when_explicit_flags_are_present(
    monkeypatch,
) -> None:
    """explicit flags should skip prompt handling entirely."""

    monkeypatch.setattr(
        storage_setup,
        "_prompt_for_storage_mode",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected prompt")),
    )

    selection = storage_setup.resolve_storage_selection(
        existing_config=None,
        storage_flag="external",
        admin_dsn_flag="postgresql+psycopg://admin:secret@db.example.com:5432/shellbrain",
    )

    assert selection.runtime_mode == "external_postgres"
    assert (
        selection.admin_dsn
        == "postgresql+psycopg://admin:secret@db.example.com:5432/shellbrain"
    )


def test_resolve_storage_selection_should_reject_storage_switch_when_config_exists() -> (
    None
):
    """changing storage mode over an existing machine config should fail closed."""

    with pytest.raises(InitConflictError) as excinfo:
        storage_setup.resolve_storage_selection(
            existing_config=_managed_machine_config(),
            storage_flag="external",
            admin_dsn_flag=None,
        )

    assert "cannot switch storage modes" in str(excinfo.value)


def _managed_machine_config() -> MachineConfig:
    """Return one minimal managed machine config for storage-selection tests."""

    return MachineConfig(
        config_version=2,
        bootstrap_version=1,
        instance_id="inst-1",
        runtime_mode="managed_local",
        bootstrap_state="ready",
        current_step="verification",
        last_error=None,
        database=DatabaseState(
            app_dsn="postgresql+psycopg://app@127.0.0.1:55432/shellbrain",
            admin_dsn="postgresql+psycopg://admin@127.0.0.1:55432/shellbrain",
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


class _FakeTerminal:
    """Minimal line-oriented tty stub for prompt tests."""

    def __init__(self, lines: list[str], *, is_tty: bool = False) -> None:
        self._lines = list(lines)
        self.output: list[str] = []
        self._is_tty = is_tty

    def readline(self) -> str:
        if not self._lines:
            return ""
        return self._lines.pop(0)

    def write(self, text: str) -> int:
        self.output.append(text)
        return len(text)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        return None

    def isatty(self) -> bool:
        return self._is_tty
