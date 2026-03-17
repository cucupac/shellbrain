"""Durability contracts for DB container deletion and recreation."""

import pytest


@pytest.mark.docker
@pytest.mark.persistence
def test_container_recreate_persists_memories(isolated_db_factory) -> None:
    """persistence should preserve sentinel shellbrain data across DB container deletion and recreation."""

    environment = isolated_db_factory("container-lifecycle")
    environment.start_isolated_db()
    environment.run_migrations()
    expected = environment.seed_sentinel_dataset()

    environment.assert_sentinel_dataset(expected)
    environment.destroy_db_container()
    environment.recreate_db_container()
    environment.assert_sentinel_dataset(expected)
