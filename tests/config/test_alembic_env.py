"""Alembic environment contracts for admin/app DSN selection."""

from __future__ import annotations

import importlib
import sys
from contextlib import nullcontext

from alembic.config import Config

APP_TEST_DSN = "postgresql+psycopg://app_user:app_password@localhost:5432/app_db"
ADMIN_TEST_DSN = "postgresql+psycopg://admin_user:admin_password@localhost:5432/admin_db"


def _load_env_module(monkeypatch):
    """Import the Alembic env module under a controlled offline Alembic context."""

    import alembic.context as alembic_context

    config = Config()
    config.config_file_name = None
    monkeypatch.setattr(alembic_context, "config", config, raising=False)
    monkeypatch.setattr(alembic_context, "is_offline_mode", lambda: True, raising=False)
    monkeypatch.setattr(alembic_context, "configure", lambda **kwargs: None, raising=False)
    monkeypatch.setattr(alembic_context, "begin_transaction", lambda: nullcontext(), raising=False)
    monkeypatch.setattr(alembic_context, "run_migrations", lambda: None, raising=False)
    sys.modules.pop("app.migrations.env", None)
    module = importlib.import_module("app.migrations.env")
    return importlib.reload(module)


def test_alembic_env_should_prefer_admin_dsn(monkeypatch) -> None:
    """alembic env should route migrations through the admin DSN when present."""

    monkeypatch.setenv("SHELLBRAIN_DB_DSN", APP_TEST_DSN)
    monkeypatch.setenv("SHELLBRAIN_DB_ADMIN_DSN", ADMIN_TEST_DSN)

    module = _load_env_module(monkeypatch)

    assert module.config.get_main_option("sqlalchemy.url") == ADMIN_TEST_DSN


def test_alembic_env_should_fall_back_to_app_dsn_when_admin_is_missing(monkeypatch) -> None:
    """alembic env should still support the single-DSN fallback when no admin DSN exists."""

    monkeypatch.setenv("SHELLBRAIN_DB_DSN", APP_TEST_DSN)
    monkeypatch.delenv("SHELLBRAIN_DB_ADMIN_DSN", raising=False)

    module = _load_env_module(monkeypatch)

    assert module.config.get_main_option("sqlalchemy.url") == APP_TEST_DSN
