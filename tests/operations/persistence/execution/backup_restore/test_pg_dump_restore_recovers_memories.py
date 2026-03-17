"""Durability contracts for logical backup and restore."""

from pathlib import Path

import pytest


@pytest.mark.docker
@pytest.mark.persistence
def test_pg_dump_restore_recovers_memories(isolated_db_factory) -> None:
    """persistence should recover sentinel shellbrain data through pg_dump and restore into a fresh database."""

    source = isolated_db_factory("backup-source")
    source.start_isolated_db()
    source.run_migrations()
    expected = source.seed_sentinel_dataset()

    dump_path = source.dump_db(Path(source.dump_dir) / "shellbrain.sql")

    target = isolated_db_factory("backup-target")
    target.start_isolated_db()
    target.restore_db(dump_path)
    target.assert_sentinel_dataset(expected)
