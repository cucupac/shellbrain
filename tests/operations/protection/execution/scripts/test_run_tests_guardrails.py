"""Protection contracts for the default test runner script."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_run_tests_should_fail_fast_when_test_dsn_is_missing() -> None:
    """run_tests should refuse to start unless one disposable test DSN is configured."""

    if not _docker_is_available():
        pytest.skip("docker is required for the run_tests script path.")

    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "run_tests"
    env = {key: value for key, value in os.environ.items() if key != "SHELLBRAIN_DB_DSN_TEST"}

    completed = subprocess.run(
        ["bash", str(script_path)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "SHELLBRAIN_DB_DSN_TEST must point at an explicitly disposable test database." in completed.stderr


def test_run_tests_should_refuse_a_protected_live_dsn() -> None:
    """run_tests should abort before any DDL when the test DSN points at a protected target."""

    if not _docker_is_available():
        pytest.skip("docker is required for the run_tests script path.")

    repo_root = _repo_root()
    script_path = repo_root / "scripts" / "run_tests"
    protected_dsn = "postgresql+psycopg://admin_user:admin_password@localhost:5432/shellbrain"
    env = {
        **os.environ,
        "SHELLBRAIN_DB_DSN": protected_dsn,
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
    assert "Refusing destructive test setup against the protected live database DSN." in completed.stderr


def _docker_is_available() -> bool:
    """Return whether docker and docker compose are available for the script preflight."""

    if shutil.which("docker") is None:
        return False
    version = subprocess.run(["docker", "version"], capture_output=True, text=True, check=False)
    compose = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True, check=False)
    return version.returncode == 0 and compose.returncode == 0


def _repo_root() -> Path:
    """Resolve the repository root from the test file location."""

    return Path(__file__).resolve().parents[5]
