"""Protection contracts for the default test runner script."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import textwrap


def test_run_tests_should_refuse_the_default_test_host_when_it_matches_the_protected_live_host() -> (
    None
):
    """run_tests should refuse its generated default when it resolves to the protected live host."""

    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "run_tests"
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"SHELLBRAIN_DB_DSN_TEST", "SHELLBRAIN_DB_ADMIN_DSN_TEST"}
    }
    env["SHELLBRAIN_PROTECTED_LIVE_DSN"] = (
        "postgresql+psycopg://live_user:live_password@127.0.0.1:5433/shellbrain"
    )

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert (
        "Refusing destructive test setup against the protected live database host/port."
        in completed.stderr
    )


def test_run_tests_should_refuse_a_generated_database_prefix_that_is_not_shellbrain_owned() -> (
    None
):
    """run_tests should only generate cleanup-targeted databases with Shellbrain prefixes."""

    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "run_tests"
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"SHELLBRAIN_DB_DSN_TEST", "SHELLBRAIN_DB_ADMIN_DSN_TEST"}
    }
    env["SHELLBRAIN_TEST_DB_PREFIX"] = "tmp_"

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert (
        "SHELLBRAIN_TEST_DB_PREFIX must begin with shellbrain_test_"
        in completed.stderr
    )


def test_run_tests_should_discover_the_live_machine_config_before_switching_to_the_test_home(
    tmp_path: Path,
) -> None:
    """run_tests should still protect the live host when no explicit protected DSN is provided."""

    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "run_tests"
    config_path = tmp_path / "live-shellbrain-home" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        textwrap.dedent(
            """
            config_version = 2
            bootstrap_version = 1
            instance_id = "inst-live"
            runtime_mode = "managed_local"
            bootstrap_state = "ready"
            current_step = ""
            last_error = ""

            [database]
            app_dsn = "postgresql+psycopg://live_app:live_password@127.0.0.1:5433/shellbrain"
            admin_dsn = "postgresql+psycopg://live_admin:live_password@127.0.0.1:5433/shellbrain"

            [managed]
            instance_id = "inst-live"
            container_name = "shellbrain-postgres-live"
            image = "pgvector/pgvector:pg16"
            host = "127.0.0.1"
            port = 5433
            db_name = "shellbrain"
            data_dir = "/tmp/shellbrain-live-data"
            admin_user = "live_admin"
            admin_password = "live_password"
            app_user = "live_app"
            app_password = "live_password"

            [backups]
            root = "/tmp/shellbrain-backups"
            mirror_root = ""

            [embeddings]
            provider = "stub"
            model = "stub"
            model_revision = ""
            backend_version = ""
            cache_path = "/tmp/shellbrain-models"
            readiness_state = "ready"
            last_error = ""
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "SHELLBRAIN_DB_DSN_TEST",
            "SHELLBRAIN_DB_ADMIN_DSN_TEST",
            "SHELLBRAIN_PROTECTED_LIVE_DSN",
            "SHELLBRAIN_HOME",
        }
    }
    env["SHELLBRAIN_LIVE_MACHINE_CONFIG_PATH"] = str(config_path)

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert (
        "Refusing destructive test setup against the protected live database host/port."
        in completed.stderr
    )


def test_run_tests_should_fail_closed_when_the_live_machine_config_is_missing(
    tmp_path: Path,
) -> None:
    """run_tests should not proceed when no protected live DSN can be resolved."""

    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "run_tests"
    missing_config_path = tmp_path / "missing-shellbrain-home" / "config.toml"
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "SHELLBRAIN_DB_DSN_TEST",
            "SHELLBRAIN_DB_ADMIN_DSN_TEST",
            "SHELLBRAIN_PROTECTED_LIVE_DSN",
            "SHELLBRAIN_HOME",
        }
    }
    env["SHELLBRAIN_LIVE_MACHINE_CONFIG_PATH"] = str(missing_config_path)

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "live machine config" in completed.stderr
    assert "could not be resolved" in completed.stderr


def test_run_tests_should_fail_closed_when_the_live_machine_config_is_invalid(
    tmp_path: Path,
) -> None:
    """run_tests should not treat a corrupt live config as absence of a live target."""

    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "run_tests"
    config_path = tmp_path / "live-shellbrain-home" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("runtime_mode = [", encoding="utf-8")
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "SHELLBRAIN_DB_DSN_TEST",
            "SHELLBRAIN_DB_ADMIN_DSN_TEST",
            "SHELLBRAIN_PROTECTED_LIVE_DSN",
            "SHELLBRAIN_HOME",
        }
    }
    env["SHELLBRAIN_LIVE_MACHINE_CONFIG_PATH"] = str(config_path)

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "live machine config" in completed.stderr
    assert "invalid" in completed.stderr


def test_ci_tests_job_should_provide_an_explicit_protected_live_dsn() -> None:
    """CI must satisfy run_tests' fail-closed live-target requirement explicitly."""

    workflow = (_repo_root() / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "SHELLBRAIN_PROTECTED_LIVE_DSN:" in workflow
    assert "127.0.0.1:5432/shellbrain" in workflow


def test_run_tests_should_refuse_a_protected_live_dsn() -> None:
    """run_tests should abort before any DDL when the test DSN points at a protected target."""

    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "run_tests"
    protected_dsn = (
        "postgresql+psycopg://admin_user:admin_password@localhost:5432/shellbrain"
    )
    env = {
        **os.environ,
        "SHELLBRAIN_PROTECTED_LIVE_DSN": protected_dsn,
        "SHELLBRAIN_DB_DSN_TEST": protected_dsn,
    }

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert (
        "Refusing destructive test setup against the protected live database DSN."
        in completed.stderr
    )


def test_run_tests_should_refuse_a_test_dsn_on_the_live_host_even_with_a_different_database_name() -> (
    None
):
    """run_tests should reject host/port collisions before destructive setup."""

    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "run_tests"
    env = {
        **os.environ,
        "SHELLBRAIN_PROTECTED_LIVE_DSN": "postgresql+psycopg://live_user:live_password@127.0.0.1:55432/shellbrain",
        "SHELLBRAIN_DB_DSN_TEST": "postgresql+psycopg://test_user:test_password@127.0.0.1:55432/shellbrain_test_safe",
    }

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert (
        "Refusing destructive test setup against the protected live database host/port."
        in completed.stderr
    )


def _repo_root() -> Path:
    """Resolve the repository root from the test file location."""

    return Path(__file__).resolve().parents[5]
