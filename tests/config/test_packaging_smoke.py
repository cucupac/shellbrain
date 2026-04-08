"""Clean-room packaging and install smoke coverage for the public CLI."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import psycopg
import pytest


_LIGHTWEIGHT_RUNTIME_DEPS = [
    "SQLAlchemy>=2.0,<3.0",
    "alembic>=1.13,<2.0",
    "pydantic>=2.7,<3.0",
    "PyYAML>=6.0,<7.0",
    "psycopg[binary]>=3.1,<4.0",
    "pgvector>=0.3,<1.0",
]


def test_editable_install_should_expose_shellbrain_help_in_a_clean_room(tmp_path: Path) -> None:
    """editable installs should expose the shellbrain console script outside this repository."""

    repo_root = _repo_root()
    external_repo = tmp_path / "external-editable-repo"
    external_repo.mkdir()
    python_executable, shellbrain_executable = _create_isolated_install(
        tmp_path=tmp_path,
        name="editable-install",
        install_spec=str(repo_root),
        editable=True,
        install_runtime_deps=False,
    )

    completed = subprocess.run(
        [shellbrain_executable, "--help"],
        check=True,
        cwd=external_repo,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )

    assert python_executable.exists()
    assert shellbrain_executable.exists()
    assert "shellbrain admin migrate" in completed.stdout
    assert "shellbrain upgrade" in completed.stdout
    assert "events` before every write" in completed.stdout


def test_git_file_install_should_expose_shellbrain_help_in_a_clean_room(tmp_path: Path) -> None:
    """git-url installs should expose the shellbrain console script outside this repository."""

    if shutil.which("git") is None:
        pytest.skip("git is required for git+file install smoke tests")

    repo_root = _repo_root()
    git_snapshot = _prepare_git_snapshot(tmp_path, repo_root)
    external_repo = tmp_path / "external-git-repo"
    external_repo.mkdir()
    _, shellbrain_executable = _create_isolated_install(
        tmp_path=tmp_path,
        name="git-install",
        install_spec=f"git+file://{git_snapshot}",
        editable=False,
        install_runtime_deps=False,
    )

    completed = subprocess.run(
        [shellbrain_executable, "--help"],
        check=True,
        cwd=external_repo,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )

    assert shellbrain_executable.exists()
    assert "Typical workflow" in completed.stdout
    assert "shellbrain upgrade" in completed.stdout
    assert "read" in completed.stdout
    assert "events" in completed.stdout


def test_editable_install_should_package_onboarding_assets_in_a_clean_room(tmp_path: Path) -> None:
    """editable installs should expose packaged onboarding assets through importlib.resources."""

    repo_root = _repo_root()
    external_repo = tmp_path / "external-assets-repo"
    external_repo.mkdir()
    python_executable, _ = _create_isolated_install(
        tmp_path=tmp_path,
        name="assets-install",
        install_spec=str(repo_root),
        editable=True,
        install_runtime_deps=False,
    )

    completed = subprocess.run(
        [
            str(python_executable),
            "-c",
            (
                "from importlib import resources; "
                "root = resources.files('app.onboarding_assets'); "
                "print(root.joinpath('codex', 'shellbrain-session-start', 'agents', 'openai.yaml').read_text()); "
                "print(root.joinpath('codex', 'shellbrain-session-start', 'assets', 'shellbrain_logo.png').is_file()); "
                "print(root.joinpath('claude', 'skills', 'shellbrain-session-start', 'SKILL.md').read_text().splitlines()[0]); "
                "print(root.joinpath('codex', 'shellbrain-usage-review', 'agents', 'openai.yaml').read_text()); "
                "print(root.joinpath('codex', 'shellbrain-usage-review', 'assets', 'shellbrain_logo.png').is_file()); "
                "print(root.joinpath('claude', 'skills', 'shellbrain-usage-review', 'SKILL.md').read_text().splitlines()[0])"
            ),
        ],
        check=True,
        cwd=external_repo,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )

    assert 'display_name: "Shellbrain Session Start"' in completed.stdout
    assert "True" in completed.stdout
    assert "# Shellbrain Session Start" in completed.stdout
    assert 'display_name: "Shellbrain Usage Review"' in completed.stdout
    assert "# Shellbrain Usage Review" in completed.stdout


def test_git_file_install_should_package_onboarding_assets_in_a_clean_room(tmp_path: Path) -> None:
    """git-url installs should also carry the packaged onboarding assets."""

    if shutil.which("git") is None:
        pytest.skip("git is required for git+file install smoke tests")

    repo_root = _repo_root()
    git_snapshot = _prepare_git_snapshot(tmp_path, repo_root)
    external_repo = tmp_path / "external-assets-git-repo"
    external_repo.mkdir()
    python_executable, _ = _create_isolated_install(
        tmp_path=tmp_path,
        name="assets-git-install",
        install_spec=f"git+file://{git_snapshot}",
        editable=False,
        install_runtime_deps=False,
    )

    completed = subprocess.run(
        [
            str(python_executable),
            "-c",
            (
                "from importlib import resources; "
                "root = resources.files('app.onboarding_assets'); "
                "print(root.joinpath('codex', 'shellbrain-session-start', 'agents', 'openai.yaml').read_text()); "
                "print(root.joinpath('codex', 'shellbrain-session-start', 'assets', 'shellbrain_logo.png').is_file()); "
                "print(root.joinpath('claude', 'skills', 'shellbrain-session-start', 'SKILL.md').read_text().splitlines()[0]); "
                "print(root.joinpath('codex', 'shellbrain-usage-review', 'agents', 'openai.yaml').read_text()); "
                "print(root.joinpath('codex', 'shellbrain-usage-review', 'assets', 'shellbrain_logo.png').is_file()); "
                "print(root.joinpath('claude', 'skills', 'shellbrain-usage-review', 'SKILL.md').read_text().splitlines()[0])"
            ),
        ],
        check=True,
        cwd=external_repo,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )

    assert 'display_name: "Shellbrain Session Start"' in completed.stdout
    assert "True" in completed.stdout
    assert "# Shellbrain Session Start" in completed.stdout
    assert 'display_name: "Shellbrain Usage Review"' in completed.stdout
    assert "# Shellbrain Usage Review" in completed.stdout


def test_admin_migrate_should_initialize_schema_from_an_installed_package(tmp_path: Path) -> None:
    """installed-package admin migrate should initialize an empty database from packaged artifacts."""

    base_dsn = os.getenv("SHELLBRAIN_DB_DSN_TEST")
    admin_base_dsn = os.getenv("SHELLBRAIN_DB_ADMIN_DSN_TEST", base_dsn or "")
    if not base_dsn or not admin_base_dsn:
        pytest.skip("Set SHELLBRAIN_DB_DSN_TEST to run packaging migration smoke tests.")

    repo_root = _repo_root()
    external_repo = tmp_path / "external-migrate-repo"
    external_repo.mkdir()
    _, shellbrain_executable = _create_isolated_install(
        tmp_path=tmp_path,
        name="migrate-install",
        install_spec=str(repo_root),
        editable=True,
        install_runtime_deps=True,
    )

    package_dsn, admin_dsn, db_name = _create_temp_database(base_dsn, admin_base_dsn)
    package_admin_dsn = _replace_database_dsn(admin_base_dsn, db_name)
    try:
        completed = subprocess.run(
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
                cur.execute("SELECT to_regclass('public.memories');")
                memories_table = cur.fetchone()[0]
                cur.execute("SELECT to_regclass('public.episode_events');")
                episode_events_table = cur.fetchone()[0]
                cur.execute("SELECT version_num FROM alembic_version;")
                alembic_version = cur.fetchone()[0]

        assert memories_table is not None
        assert episode_events_table is not None
        assert alembic_version == "20260320_0008"
        assert "Applied shellbrain schema migrations to head." in completed.stdout
    finally:
        _drop_temp_database(admin_dsn, db_name)


def _create_isolated_install(
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
    python_executable = _venv_python(venv_dir)
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
            [str(python_executable), "-m", "pip", "install", * _LIGHTWEIGHT_RUNTIME_DEPS],
            check=True,
            capture_output=True,
            text=True,
        )

    return python_executable, _venv_shellbrain(venv_dir)


def _create_temp_database(base_dsn: str, admin_base_dsn: str | None = None) -> tuple[str, str, str]:
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


def _drop_temp_database(admin_dsn: str, db_name: str) -> None:
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


def _replace_database_dsn(dsn: str, db_name: str) -> str:
    """Return one DSN string with the database path swapped to a named database."""

    parsed = urlparse(dsn.replace("+psycopg", ""))
    return urlunparse(parsed._replace(path=f"/{db_name}")).replace("postgresql://", "postgresql+psycopg://", 1)


def _repo_root() -> Path:
    """Resolve the repository root for clean-room install commands."""

    return Path(__file__).resolve().parents[2]


def _prepare_git_snapshot(tmp_path: Path, repo_root: Path) -> Path:
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


def _venv_python(venv_dir: Path) -> Path:
    """Resolve the Python executable inside one virtualenv."""

    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_shellbrain(venv_dir: Path) -> Path:
    """Resolve the shellbrain console script inside one virtualenv."""

    if os.name == "nt":
        return venv_dir / "Scripts" / "app.exe"
    return venv_dir / "bin" / "shellbrain"
