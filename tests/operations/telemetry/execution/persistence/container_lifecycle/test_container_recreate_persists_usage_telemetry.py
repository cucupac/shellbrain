"""Durability contracts for telemetry across DB container recreation."""

import pytest

from tests.operations._shared.telemetry_db_fixtures import (
    assert_usage_telemetry_dataset_via_dsn,
    seed_usage_telemetry_dataset_via_dsn,
)


@pytest.mark.docker
@pytest.mark.persistence
def test_container_recreate_persists_usage_telemetry(isolated_db_factory) -> None:
    """persistence should preserve sentinel usage telemetry rows across DB container deletion and recreation."""

    environment = isolated_db_factory("telemetry-container-lifecycle")
    environment.start_isolated_db()
    environment.run_migrations()
    expected = seed_usage_telemetry_dataset_via_dsn(environment.dsn)

    assert_usage_telemetry_dataset_via_dsn(environment.dsn, expected)
    environment.destroy_db_container()
    environment.recreate_db_container()
    assert_usage_telemetry_dataset_via_dsn(environment.dsn, expected)
