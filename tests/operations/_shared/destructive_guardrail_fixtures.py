"""Helpers that prevent destructive test flows from touching protected databases."""

from __future__ import annotations

import os

from shellbrain.periphery.admin.instance_guard import (
    TEST,
    assert_destructive_allowed,
    assert_disposable_test_dsn,
    ensure_instance_metadata,
)


def assert_test_database_is_disposable(test_dsn: str) -> None:
    """Refuse to run destructive setup against protected or production-shaped DBs."""

    assert_disposable_test_dsn(
        test_dsn=test_dsn,
        protected_dsn=(
            os.getenv("SHELLBRAIN_PROTECTED_LIVE_DSN")
            or os.getenv("SHELLBRAIN_DB_DSN")
        ),
    )


def stamp_test_instance(test_dsn: str) -> None:
    """Classify one migrated integration database as an explicit test instance."""

    admin_dsn = (
        os.getenv("SHELLBRAIN_DB_ADMIN_DSN_TEST")
        or os.getenv("SHELLBRAIN_DB_ADMIN_DSN")
        or test_dsn
    )
    ensure_instance_metadata(
        admin_dsn,
        instance_mode=TEST,
        created_by="tests.integration",
        notes="Disposable integration test database.",
    )


def assert_destructive_test_setup_allowed(test_dsn: str) -> None:
    """Refuse destructive cleanup unless the instance is explicitly stamped test."""

    assert_destructive_allowed(test_dsn, allowed_modes=(TEST,))
