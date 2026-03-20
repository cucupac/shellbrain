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


def test_instance_guard_should_reject_the_protected_live_fingerprint() -> None:
    """instance guard should refuse the exact protected live DSN."""

    protected = "postgresql+psycopg://shellbrain_admin:shellbrain_admin@localhost:5432/shellbrain"

    with pytest.raises(RuntimeError, match="protected live database DSN"):
        assert_disposable_test_dsn(test_dsn=protected, protected_dsn=protected)


@pytest.mark.parametrize(
    ("dsn", "database_name"),
    [
        ("postgresql+psycopg://tester:pw@localhost:5432/shellbrain", "shellbrain"),
        ("postgresql+psycopg://tester:pw@localhost:5432/memory", "memory"),
    ],
)
def test_instance_guard_should_reject_protected_database_names(dsn: str, database_name: str) -> None:
    """instance guard should refuse production-shaped database names even without a live fingerprint."""

    with pytest.raises(RuntimeError, match=database_name):
        assert_disposable_test_dsn(test_dsn=dsn)


def test_instance_guard_fingerprint_should_ignore_role_username() -> None:
    """instance fingerprinting should classify one DB independently of app/admin role usernames."""

    app_dsn = "postgresql+psycopg://shellbrain_app:shellbrain@localhost:5432/shellbrain"
    admin_dsn = "postgresql+psycopg://shellbrain_admin:shellbrain_admin@localhost:5432/shellbrain"

    assert dsn_fingerprint(app_dsn) == dsn_fingerprint(admin_dsn)


def test_destructive_guard_should_fail_closed_when_metadata_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """destructive guard should refuse databases that are not explicitly stamped disposable."""

    monkeypatch.setattr("app.periphery.admin.instance_guard.fetch_instance_metadata", lambda dsn: None)

    with pytest.raises(RuntimeError, match="instance metadata is missing"):
        assert_destructive_allowed("postgresql+psycopg://tester:pw@localhost:5432/test_db")


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
        assert_destructive_allowed("postgresql+psycopg://tester:pw@localhost:5432/test_db")


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

    assert_destructive_allowed("postgresql+psycopg://tester:pw@localhost:5432/test_db")
