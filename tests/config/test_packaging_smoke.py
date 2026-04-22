"""Clean-room packaging and install smoke coverage for the public CLI."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import psycopg
import pytest
from tests._shared.packaging_smoke_helpers import (
    create_isolated_install,
    create_temp_database,
    drop_temp_database,
    prepare_git_snapshot,
    replace_database_dsn,
    repo_root as resolve_repo_root,
)


def test_editable_install_should_expose_shellbrain_help_in_a_clean_room(tmp_path: Path) -> None:
    """editable installs should expose the shellbrain console script outside this repository."""

    repo_root = resolve_repo_root()
    external_repo = tmp_path / "external-editable-repo"
    external_repo.mkdir()
    python_executable, shellbrain_executable = create_isolated_install(
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

    repo_root = resolve_repo_root()
    git_snapshot = prepare_git_snapshot(tmp_path, repo_root)
    external_repo = tmp_path / "external-git-repo"
    external_repo.mkdir()
    _, shellbrain_executable = create_isolated_install(
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

    repo_root = resolve_repo_root()
    external_repo = tmp_path / "external-assets-repo"
    external_repo.mkdir()
    python_executable, _ = create_isolated_install(
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

    repo_root = resolve_repo_root()
    git_snapshot = prepare_git_snapshot(tmp_path, repo_root)
    external_repo = tmp_path / "external-assets-git-repo"
    external_repo.mkdir()
    python_executable, _ = create_isolated_install(
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

    repo_root = resolve_repo_root()
    external_repo = tmp_path / "external-migrate-repo"
    external_repo.mkdir()
    _, shellbrain_executable = create_isolated_install(
        tmp_path=tmp_path,
        name="migrate-install",
        install_spec=str(repo_root),
        editable=True,
        install_runtime_deps=True,
    )

    package_dsn, admin_dsn, db_name = create_temp_database(base_dsn, admin_base_dsn)
    package_admin_dsn = replace_database_dsn(admin_base_dsn, db_name)
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
                cur.execute("SELECT to_regclass('public.concepts');")
                concepts_table = cur.fetchone()[0]
                cur.execute("SELECT version_num FROM alembic_version;")
                alembic_version = cur.fetchone()[0]

        assert memories_table is not None
        assert episode_events_table is not None
        assert concepts_table is not None
        assert alembic_version == "20260422_0014"
        assert "Applied shellbrain schema migrations to head." in completed.stdout
    finally:
        drop_temp_database(admin_dsn, db_name)


def test_admin_migrate_should_preserve_pre_frontier_data_and_enable_frontier_support(
    tmp_path: Path,
) -> None:
    """installed-package admin migrate should preserve 0008 data and widen constraints for frontier."""

    base_dsn = os.getenv("SHELLBRAIN_DB_DSN_TEST")
    admin_base_dsn = os.getenv("SHELLBRAIN_DB_ADMIN_DSN_TEST", base_dsn or "")
    if not base_dsn or not admin_base_dsn:
        pytest.skip("Set SHELLBRAIN_DB_DSN_TEST to run packaging migration smoke tests.")

    repo_root = resolve_repo_root()
    external_repo = tmp_path / "external-frontier-migrate-repo"
    external_repo.mkdir()
    python_executable, shellbrain_executable = create_isolated_install(
        tmp_path=tmp_path,
        name="frontier-migrate-install",
        install_spec=str(repo_root),
        editable=True,
        install_runtime_deps=True,
    )

    package_dsn, admin_dsn, db_name = create_temp_database(base_dsn, admin_base_dsn)
    package_admin_dsn = replace_database_dsn(admin_base_dsn, db_name)
    shellbrain_home = tmp_path / ".shellbrain-home-frontier-migrate"
    command_env = {
        **os.environ,
        "SHELLBRAIN_DB_DSN": package_dsn,
        "SHELLBRAIN_DB_ADMIN_DSN": package_admin_dsn,
        "SHELLBRAIN_INSTANCE_MODE": "test",
        "SHELLBRAIN_HOME": str(shellbrain_home),
    }
    raw_package_dsn = package_dsn.replace("+psycopg", "")

    try:
        subprocess.run(
            [
                str(python_executable),
                "-c",
                "from app.boot.migrations import upgrade_database; upgrade_database('20260320_0008')",
            ],
            check=True,
            cwd=external_repo,
            text=True,
            capture_output=True,
            env=command_env,
        )

        with psycopg.connect(raw_package_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version_num FROM alembic_version;")
                assert cur.fetchone()[0] == "20260320_0008"
                cur.execute(
                    """
                    INSERT INTO memories (id, repo_id, scope, kind, text)
                    VALUES
                      ('pre0009-problem', 'example/repo', 'repo', 'problem', 'pre-frontier problem'),
                      ('pre0009-fact', 'example/repo', 'repo', 'fact', 'pre-frontier fact')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO association_edges (id, repo_id, from_memory_id, to_memory_id, relation_type)
                    VALUES ('pre0009-edge', 'example/repo', 'pre0009-problem', 'pre0009-fact', 'depends_on')
                    """
                )

        with psycopg.connect(raw_package_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                with pytest.raises(psycopg.Error):
                    cur.execute(
                        """
                        INSERT INTO memories (id, repo_id, scope, kind, text)
                        VALUES ('frontier-before-upgrade', 'example/repo', 'repo', 'frontier', 'should fail before 0009')
                        """
                    )

        completed = subprocess.run(
            [shellbrain_executable, "admin", "migrate"],
            check=True,
            cwd=external_repo,
            text=True,
            capture_output=True,
            env=command_env,
        )

        with psycopg.connect(raw_package_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version_num FROM alembic_version;")
                assert cur.fetchone()[0] == "20260422_0014"

                cur.execute("SELECT kind, text FROM memories WHERE id = 'pre0009-problem';")
                assert cur.fetchone() == ("problem", "pre-frontier problem")

                cur.execute("SELECT kind, text FROM memories WHERE id = 'pre0009-fact';")
                assert cur.fetchone() == ("fact", "pre-frontier fact")

                cur.execute("SELECT relation_type FROM association_edges WHERE id = 'pre0009-edge';")
                assert cur.fetchone() == ("depends_on",)

                cur.execute(
                    """
                    INSERT INTO memories (id, repo_id, scope, kind, text)
                    VALUES
                      ('frontier-after-upgrade', 'example/repo', 'repo', 'frontier', 'frontier now allowed'),
                      ('mature-after-upgrade', 'example/repo', 'repo', 'fact', 'mature target')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO association_edges (id, repo_id, from_memory_id, to_memory_id, relation_type)
                    VALUES ('matures-into-edge', 'example/repo', 'frontier-after-upgrade', 'mature-after-upgrade', 'matures_into')
                    """
                )
                cur.execute(
                    """
                    INSERT INTO association_observations (
                      id, repo_id, edge_id, from_memory_id, to_memory_id, relation_type, source, valence
                    )
                    VALUES (
                      'matures-into-observation',
                      'example/repo',
                      'matures-into-edge',
                      'frontier-after-upgrade',
                      'mature-after-upgrade',
                      'matures_into',
                      'agent_explicit',
                      1.0
                    )
                    """
                )

                cur.execute("SELECT kind FROM memories WHERE id = 'frontier-after-upgrade';")
                assert cur.fetchone() == ("frontier",)

                cur.execute("SELECT relation_type FROM association_edges WHERE id = 'matures-into-edge';")
                assert cur.fetchone() == ("matures_into",)

                cur.execute("SELECT relation_type FROM association_observations WHERE id = 'matures-into-observation';")
                assert cur.fetchone() == ("matures_into",)

        assert "Applied shellbrain schema migrations to head." in completed.stdout
    finally:
        drop_temp_database(admin_dsn, db_name)
