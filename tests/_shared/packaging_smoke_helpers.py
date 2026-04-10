"""Shared helpers for clean-room packaging smoke tests."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import psycopg


_LIGHTWEIGHT_RUNTIME_DEPS = [
    "SQLAlchemy>=2.0,<3.0",
    "alembic>=1.13,<2.0",
    "pydantic>=2.7,<3.0",
    "PyYAML>=6.0,<7.0",
    "psycopg[binary]>=3.1,<4.0",
    "pgvector>=0.3,<1.0",
]


def create_isolated_install(
    *,
    tmp_path: Path,
    name: str,
    install_spec: str,
    editable: bool,
    install_runtime_deps: bool,
) -> tuple[Path, Path]:
    """Create one clean-room virtualenv and install the packaged CLI into it."""

    venv_dir = tmp_path / name
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True, capture_output=True, text=True)
    python_executable = venv_python(venv_dir)
    subprocess.run(
        [str(python_executable), "-m", "pip", "install", "setuptools>=69.0", "wheel"],
        check=True,
        capture_output=True,
        text=True,
    )

    install_command = [str(python_executable), "-m", "pip", "install", "--no-build-isolation", "--no-deps"]
    if editable:
        install_command.extend(["-e", install_spec])
    else:
        install_command.append(install_spec)
    subprocess.run(install_command, check=True, capture_output=True, text=True)

    if install_runtime_deps:
        subprocess.run(
            [str(python_executable), "-m", "pip", "install", *_LIGHTWEIGHT_RUNTIME_DEPS],
            check=True,
            capture_output=True,
            text=True,
        )

    return python_executable, venv_shellbrain(venv_dir)


def create_temp_database(base_dsn: str, admin_base_dsn: str | None = None) -> tuple[str, str, str]:
    """Create one disposable database alongside the configured test server."""

    raw_base_dsn = base_dsn.replace("+psycopg", "")
    parsed = urlparse(raw_base_dsn)
    admin_parsed = urlparse((admin_base_dsn or base_dsn).replace("+psycopg", ""))
    db_name = f"shellbrain_pkg_{uuid4().hex[:8]}"
    admin_dsn = urlunparse(admin_parsed._replace(path="/postgres"))
    package_dsn = urlunparse(parsed._replace(path=f"/{db_name}"))

    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{db_name}"')

    return package_dsn.replace("postgresql://", "postgresql+psycopg://", 1), admin_dsn, db_name


def drop_temp_database(admin_dsn: str, db_name: str) -> None:
    """Drop one disposable smoke-test database and terminate leftover sessions."""

    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
            """,
            (db_name,),
        )
        conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')


def replace_database_dsn(dsn: str, db_name: str) -> str:
    """Return one DSN string with the database path swapped to a named database."""

    parsed = urlparse(dsn.replace("+psycopg", ""))
    return urlunparse(parsed._replace(path=f"/{db_name}")).replace("postgresql://", "postgresql+psycopg://", 1)


def repo_root() -> Path:
    """Resolve the repository root for clean-room install commands."""

    return Path(__file__).resolve().parents[2]


def prepare_git_snapshot(tmp_path: Path, repo_root: Path) -> Path:
    """Create one temporary git repository that reflects the current working tree state."""

    snapshot_root = tmp_path / "git-install-source"
    shutil.copytree(
        repo_root,
        snapshot_root,
        ignore=shutil.ignore_patterns(
            ".git",
            "env",
            ".venv",
            "__pycache__",
            ".pytest_cache",
            ".local",
        ),
    )
    subprocess.run(["git", "init"], check=True, cwd=snapshot_root, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "smoke@example.com"], check=True, cwd=snapshot_root, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Packaging Smoke"], check=True, cwd=snapshot_root, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], check=True, cwd=snapshot_root, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "snapshot"], check=True, cwd=snapshot_root, capture_output=True, text=True)
    return snapshot_root


def venv_python(venv_dir: Path) -> Path:
    """Resolve the Python executable inside one virtualenv."""

    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def venv_shellbrain(venv_dir: Path) -> Path:
    """Resolve the shellbrain console script inside one virtualenv."""

    if os.name == "nt":
        return venv_dir / "Scripts" / "app.exe"
    return venv_dir / "bin" / "shellbrain"
