"""Packaging-smoke contracts for telemetry schema artifacts."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import psycopg
import pytest

from tests._shared.packaging_smoke_helpers import (
    create_isolated_install,
    create_temp_database,
    drop_temp_database,
    replace_database_dsn,
    repo_root as resolve_repo_root,
)


def test_installed_package_admin_migrate_should_initialize_the_usage_telemetry_tables_and_views_from_packaged_artifacts(
    tmp_path: Path,
) -> None:
    """installed-package admin migrate should initialize the usage telemetry tables and views from packaged artifacts."""

    base_dsn = os.getenv("SHELLBRAIN_DB_DSN_TEST")
    admin_base_dsn = os.getenv("SHELLBRAIN_DB_ADMIN_DSN_TEST", base_dsn or "")
    if not base_dsn or not admin_base_dsn:
        pytest.skip(
            "Set SHELLBRAIN_DB_DSN_TEST to run packaging migration smoke tests."
        )

    repo_root = resolve_repo_root()
    external_repo = tmp_path / "external-telemetry-migrate-repo"
    external_repo.mkdir()
    _, shellbrain_executable = create_isolated_install(
        tmp_path=tmp_path,
        name="telemetry-migrate-install",
        install_spec=str(repo_root),
        editable=True,
        install_runtime_deps=True,
    )

    package_dsn, admin_dsn, db_name = create_temp_database(base_dsn, admin_base_dsn)
    package_admin_dsn = replace_database_dsn(admin_base_dsn, db_name)
    try:
        subprocess.run(
            [shellbrain_executable, "admin", "migrate"],
            check=True,
            cwd=external_repo,
            text=True,
            capture_output=True,
            env={
                **os.environ,
                "SHELLBRAIN_DB_DSN": package_dsn,
                "SHELLBRAIN_DB_ADMIN_DSN": package_admin_dsn,
                "SHELLBRAIN_INSTANCE_MODE": "test",
            },
        )

        with psycopg.connect(package_dsn.replace("+psycopg", "")) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.operation_invocations');")
                operation_invocations_table = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('public.read_invocation_summaries');")
                read_summaries_table = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('public.usage_command_daily');")
                usage_command_daily_view = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('public.model_usage');")
                model_usage_table = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('public.problem_runs');")
                problem_runs_table = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('public.usage_session_tokens');")
                usage_session_tokens_view = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('public.usage_problem_tokens');")
                usage_problem_tokens_view = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('public.usage_problem_tokens_legacy');")
                usage_problem_tokens_legacy_view = cur.fetchone()[0]
                cur.execute(
                    "SELECT to_regclass('public.usage_problem_read_roi_legacy');"
                )
                usage_problem_read_roi_legacy_view = cur.fetchone()[0]
                cur.execute(
                    "SELECT to_regclass('public.usage_read_before_solve_roi_legacy');"
                )
                usage_read_before_solve_roi_legacy_view = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('public.usage_problem_run_tokens');")
                usage_problem_run_tokens_view = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('public.concepts');")
                concepts_table = cur.fetchone()[0]
                cur.execute("SELECT version_num FROM alembic_version;")
                alembic_version = cur.fetchone()[0]

        assert operation_invocations_table is not None
        assert read_summaries_table is not None
        assert usage_command_daily_view is not None
        assert model_usage_table is not None
        assert problem_runs_table is not None
        assert usage_session_tokens_view is not None
        assert usage_problem_tokens_view is None
        assert usage_problem_tokens_legacy_view is not None
        assert usage_problem_read_roi_legacy_view is not None
        assert usage_read_before_solve_roi_legacy_view is not None
        assert usage_problem_run_tokens_view is not None
        assert concepts_table is not None
        assert alembic_version == "20260515_0019"
    finally:
        drop_temp_database(admin_dsn, db_name)
