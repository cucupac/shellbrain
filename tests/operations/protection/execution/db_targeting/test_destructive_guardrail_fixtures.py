"""Protection contracts for destructive test guardrail fixtures."""

from __future__ import annotations

import pytest

from tests.operations._shared.destructive_guardrail_fixtures import (
    assert_test_database_is_disposable,
)


PROTECTED_DSN = (
    "postgresql+psycopg://admin_user:admin_password@localhost:5432/shellbrain"
)
DISPOSABLE_TEST_DSN = (
    "postgresql+psycopg://test_user:test_password@localhost:5432/test_db"
)


def test_fixture_guard_should_not_treat_the_test_dsn_as_protected_when_env_points_at_the_same_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration fixtures should not self-block when SHELLBRAIN_DB_DSN matches the test target."""

    monkeypatch.delenv("SHELLBRAIN_PROTECTED_LIVE_DSN", raising=False)
    monkeypatch.setenv("SHELLBRAIN_DB_DSN", DISPOSABLE_TEST_DSN)

    assert_test_database_is_disposable(DISPOSABLE_TEST_DSN)


def test_fixture_guard_should_still_use_shellbrain_db_dsn_as_a_fallback_protected_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration fixtures should still refuse destructive setup against a distinct protected fallback."""

    monkeypatch.delenv("SHELLBRAIN_PROTECTED_LIVE_DSN", raising=False)
    monkeypatch.setenv("SHELLBRAIN_DB_DSN", PROTECTED_DSN)

    with pytest.raises(RuntimeError, match="protected live database host/port"):
        assert_test_database_is_disposable(DISPOSABLE_TEST_DSN)
