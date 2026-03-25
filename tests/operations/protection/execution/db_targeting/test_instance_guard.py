"""Protection contracts for instance metadata and destructive guardrails."""

from __future__ import annotations

import pytest

from app.periphery.admin.instance_guard import (
    InstanceMetadataRecord,
    LIVE,
    TEST,
    assert_destructive_allowed,
    assert_disposable_test_dsn,
    dsn_fingerprint,
)

PROTECTED_DSN = "postgresql+psycopg://admin_user:admin_password@localhost:5432/shellbrain"
APP_TEST_DSN = "postgresql+psycopg://app_user:app_password@localhost:5432/shellbrain"
DISPOSABLE_TEST_DSN = "postgresql+psycopg://test_user:test_password@localhost:5432/test_db"


def test_instance_guard_should_reject_the_protected_live_fingerprint() -> None:
    """instance guard should refuse the exact protected live DSN."""

    with pytest.raises(RuntimeError, match="protected live database DSN"):
        assert_disposable_test_dsn(test_dsn=PROTECTED_DSN, protected_dsn=PROTECTED_DSN)


@pytest.mark.parametrize(
    ("dsn", "database_name"),
    [
        ("postgresql+psycopg://test_user:test_password@localhost:5432/shellbrain", "shellbrain"),
        ("postgresql+psycopg://test_user:test_password@localhost:5432/memory", "memory"),
    ],
)
def test_instance_guard_should_reject_protected_database_names(dsn: str, database_name: str) -> None:
    """instance guard should refuse production-shaped database names even without a live fingerprint."""

    with pytest.raises(RuntimeError, match=database_name):
        assert_disposable_test_dsn(test_dsn=dsn)


def test_instance_guard_fingerprint_should_ignore_role_username() -> None:
    """instance fingerprinting should classify one DB independently of app/admin role usernames."""

    assert dsn_fingerprint(APP_TEST_DSN) == dsn_fingerprint(PROTECTED_DSN)


def test_destructive_guard_should_fail_closed_when_metadata_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """destructive guard should refuse databases that are not explicitly stamped disposable."""

    monkeypatch.setattr("app.periphery.admin.instance_guard.fetch_instance_metadata", lambda dsn: None)

    with pytest.raises(RuntimeError, match="instance metadata is missing"):
        assert_destructive_allowed(DISPOSABLE_TEST_DSN)


def test_destructive_guard_should_refuse_live_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    """destructive guard should never allow automation against live instances."""

    monkeypatch.setattr(
        "app.periphery.admin.instance_guard.fetch_instance_metadata",
        lambda dsn: InstanceMetadataRecord(
            instance_id="inst-live",
            instance_mode=LIVE,
            created_at="2026-03-19T00:00:00+00:00",
            created_by="tests",
            notes=None,
        ),
    )

    with pytest.raises(RuntimeError, match="instance_mode='live'"):
        assert_destructive_allowed(DISPOSABLE_TEST_DSN)


def test_destructive_guard_should_allow_test_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    """destructive guard should allow explicitly stamped test instances."""

    monkeypatch.setattr(
        "app.periphery.admin.instance_guard.fetch_instance_metadata",
        lambda dsn: InstanceMetadataRecord(
            instance_id="inst-test",
            instance_mode=TEST,
            created_at="2026-03-19T00:00:00+00:00",
            created_by="tests",
            notes=None,
        ),
    )

    assert_destructive_allowed(DISPOSABLE_TEST_DSN)
