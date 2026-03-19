"""Durability contracts for telemetry across local legacy-cluster migration."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.operations._shared.telemetry_db_fixtures import (
    assert_usage_telemetry_dataset_via_dsn,
    seed_usage_telemetry_dataset_via_dsn,
)
from tests.operations.persistence.execution.local_migration.test_local_postgres_migration_to_shellbrain import (
    _cleanup_project,
    _compose_up,
    _reserve_tcp_port,
    _run_packaged_migrations,
    _wait_for_container_postgres,
    _wait_for_host_postgres,
)


@pytest.mark.docker
@pytest.mark.persistence
def test_local_migration_should_preserve_sentinel_usage_telemetry_while_promoting_the_cluster_to_shellbrain_naming(
    tmp_path: Path,
) -> None:
    """local migration should preserve sentinel usage telemetry while promoting the cluster to shellbrain naming."""

    from uuid import uuid4
    import os
    import subprocess

    repo_root = Path(__file__).resolve().parents[6]
    project_id = uuid4().hex[:8]
    compose_project = f"shellbrain-telemetry-migrate-{project_id}"
    legacy_container = f"memory-postgres-{project_id}"
    shellbrain_container = f"shellbrain-postgres-{project_id}"
    port = _reserve_tcp_port()
    data_dir = tmp_path / "postgres-data"
    script_path = repo_root / "scripts" / "migrate_local_postgres_to_shellbrain"

    legacy_env = {
        **os.environ,
        "COMPOSE_PROJECT_NAME": compose_project,
        "POSTGRES_PORT": str(port),
        "POSTGRES_DB": "memory",
        "POSTGRES_USER": "memory",
        "POSTGRES_PASSWORD": "memory",
        "SHELLBRAIN_DB_DATA_DIR": str(data_dir),
        "SHELLBRAIN_DB_CONTAINER_NAME": legacy_container,
    }
    migration_env = {
        **os.environ,
        "COMPOSE_PROJECT_NAME": compose_project,
        "POSTGRES_PORT": str(port),
        "SHELLBRAIN_DB_DATA_DIR": str(data_dir),
        "OLD_POSTGRES_DB": "memory",
        "OLD_POSTGRES_USER": "memory",
        "OLD_POSTGRES_PASSWORD": "memory",
        "OLD_DB_CONTAINER_NAME": legacy_container,
        "NEW_POSTGRES_DB": "shellbrain",
        "NEW_POSTGRES_ADMIN_USER": "shellbrain_admin",
        "NEW_POSTGRES_ADMIN_PASSWORD": "shellbrain_admin",
        "NEW_POSTGRES_APP_USER": "shellbrain_app",
        "NEW_POSTGRES_APP_PASSWORD": "shellbrain",
        "SHELLBRAIN_DB_CONTAINER_NAME": shellbrain_container,
    }

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        _compose_up(repo_root, legacy_env)
        _wait_for_container_postgres(legacy_container, "memory", "memory")

        legacy_dsn = f"postgresql+psycopg://memory:memory@localhost:{port}/memory"
        _wait_for_host_postgres(legacy_dsn)
        _run_packaged_migrations(repo_root, legacy_dsn)
        expected = seed_usage_telemetry_dataset_via_dsn(legacy_dsn)

        subprocess.run(
            ["bash", str(script_path)],
            check=True,
            cwd=repo_root,
            env=migration_env,
            capture_output=True,
            text=True,
        )

        _wait_for_container_postgres(shellbrain_container, "shellbrain_admin", "shellbrain")
        shellbrain_dsn = f"postgresql+psycopg://shellbrain_app:shellbrain@localhost:{port}/shellbrain"
        assert_usage_telemetry_dataset_via_dsn(shellbrain_dsn, expected)
    finally:
        _cleanup_project(compose_project, legacy_container, shellbrain_container)
