"""Durability contracts for telemetry backup and restore."""

import pytest

from tests.operations._shared.telemetry_db_fixtures import (
    assert_usage_telemetry_dataset_via_dsn,
    seed_usage_telemetry_dataset_via_dsn,
)


@pytest.mark.docker
@pytest.mark.persistence
def test_pg_dump_restore_recovers_usage_telemetry(isolated_db_factory) -> None:
    """persistence should recover sentinel usage telemetry rows through pg_dump and restore into a fresh database."""

    source = isolated_db_factory("telemetry-backup-source")
    source.start_isolated_db()
    source.run_migrations()
    expected = seed_usage_telemetry_dataset_via_dsn(source.dsn)

    dump_path = source.dump_db(source.dump_dir / "usage-telemetry.sql")

    target = isolated_db_factory("telemetry-backup-target")
    target.start_isolated_db()
    target.restore_db(dump_path)
    assert_usage_telemetry_dataset_via_dsn(target.dsn, expected)
