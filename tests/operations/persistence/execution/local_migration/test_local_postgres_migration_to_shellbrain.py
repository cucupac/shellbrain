"""Durability contracts for migrating a legacy local cluster to shellbrain naming."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

import psycopg
import pytest

from app.core.entities.episodes import Episode, EpisodeEvent, EpisodeEventSource, EpisodeStatus
from app.core.interfaces.embeddings import IEmbeddingProvider
from app.periphery.cli.handlers import handle_create
from app.periphery.db.engine import get_engine
from app.periphery.db.session import get_session_factory
from app.periphery.db.uow import PostgresUnitOfWork


class _StubEmbeddingProvider(IEmbeddingProvider):
    """Deterministic embedding provider for migration smoke coverage."""

    def embed(self, text: str) -> list[float]:
        """Return one stable vector for any input text."""

        _ = text
        return [0.1, 0.2, 0.3, 0.4]

LEGACY_USER = "legacy_user"
LEGACY_PASSWORD = "legacy_password"
APP_USER = "app_user"
APP_PASSWORD = "app_password"
ADMIN_USER = "admin_user"
ADMIN_PASSWORD = "admin_password"


@pytest.mark.docker
@pytest.mark.persistence
def test_local_postgres_migration_to_shellbrain_preserves_existing_data(tmp_path: Path) -> None:
    """local migration should preserve legacy data while promoting the cluster to shellbrain naming."""

    repo_root = Path(__file__).resolve().parents[5]
    project_id = uuid4().hex[:8]
    compose_project = f"shellbrain-migrate-{project_id}"
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
        "POSTGRES_USER": LEGACY_USER,
        "POSTGRES_PASSWORD": LEGACY_PASSWORD,
        "SHELLBRAIN_DB_DATA_DIR": str(data_dir),
        "SHELLBRAIN_DB_CONTAINER_NAME": legacy_container,
    }
    migration_env = {
        **os.environ,
        "COMPOSE_PROJECT_NAME": compose_project,
        "POSTGRES_PORT": str(port),
        "SHELLBRAIN_DB_DATA_DIR": str(data_dir),
        "OLD_POSTGRES_DB": "memory",
        "OLD_POSTGRES_USER": LEGACY_USER,
        "OLD_POSTGRES_PASSWORD": LEGACY_PASSWORD,
        "OLD_DB_CONTAINER_NAME": legacy_container,
        "NEW_POSTGRES_DB": "shellbrain",
        "NEW_POSTGRES_ADMIN_USER": ADMIN_USER,
        "NEW_POSTGRES_ADMIN_PASSWORD": ADMIN_PASSWORD,
        "NEW_POSTGRES_APP_USER": APP_USER,
        "NEW_POSTGRES_APP_PASSWORD": APP_PASSWORD,
        "SHELLBRAIN_DB_CONTAINER_NAME": shellbrain_container,
    }

    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        port = _compose_up(repo_root, legacy_env)
        migration_env["POSTGRES_PORT"] = str(port)
        _wait_for_container_postgres(legacy_container, LEGACY_USER, "memory")

        legacy_dsn = f"postgresql+psycopg://{LEGACY_USER}:{LEGACY_PASSWORD}@localhost:{port}/memory"
        _wait_for_host_postgres(legacy_dsn)
        _run_packaged_migrations(repo_root, legacy_dsn, backup_dir=tmp_path / "backups")
        sentinel = _seed_sentinel_dataset(legacy_dsn)

        completed = subprocess.run(
            ["bash", str(script_path)],
            check=True,
            cwd=repo_root,
            env=migration_env,
            capture_output=True,
            text=True,
        )
        assert "Local Docker/Postgres migration is complete." in completed.stdout

        _wait_for_container_postgres(shellbrain_container, ADMIN_USER, "shellbrain")

        shellbrain_dsn = f"postgresql+psycopg://{APP_USER}:{APP_PASSWORD}@localhost:{port}/shellbrain"
        shellbrain_legacy_dsn = f"postgresql+psycopg://{ADMIN_USER}:{ADMIN_PASSWORD}@localhost:{port}/memory"

        assert _fetch_memory_text(shellbrain_dsn, sentinel["memory_id"]) == sentinel["memory_text"]
        assert _fetch_memory_text(shellbrain_legacy_dsn, sentinel["memory_id"]) == sentinel["memory_text"]
        assert set(_list_databases(shellbrain_dsn)) >= {"memory", "shellbrain"}

        container_rows = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert legacy_container not in container_rows
        assert shellbrain_container in container_rows
    finally:
        _cleanup_project(compose_project, legacy_container, shellbrain_container)


def _compose_up(repo_root: Path, env: dict[str, str], *, max_attempts: int = 5) -> int:
    """Start one isolated Docker Compose PostgreSQL service, retrying on host-port races."""

    for _attempt in range(max_attempts):
        completed = subprocess.run(
            ["docker", "compose", "-p", env["COMPOSE_PROJECT_NAME"], "up", "-d", "db"],
            check=False,
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            return int(env["POSTGRES_PORT"])
        if "ports are not available" not in completed.stderr or "bind: address already in use" not in completed.stderr:
            raise subprocess.CalledProcessError(
                completed.returncode,
                completed.args,
                output=completed.stdout,
                stderr=completed.stderr,
            )
        subprocess.run(
            ["docker", "compose", "-p", env["COMPOSE_PROJECT_NAME"], "down", "--remove-orphans"],
            check=False,
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
        )
        env["POSTGRES_PORT"] = str(_reserve_tcp_port())
    raise AssertionError(f"Timed out finding one free host port for {env['COMPOSE_PROJECT_NAME']}.")


def _cleanup_project(compose_project: str, legacy_container: str, shellbrain_container: str) -> None:
    """Remove containers and network created by one isolated migration smoke test."""

    for container_name in (legacy_container, shellbrain_container):
        subprocess.run(["docker", "rm", "-f", container_name], check=False, capture_output=True, text=True)
    subprocess.run(["docker", "network", "rm", f"{compose_project}_default"], check=False, capture_output=True, text=True)


def _wait_for_container_postgres(container_name: str, user_name: str, database_name: str, *, timeout_seconds: int = 60) -> None:
    """Wait for one containerized PostgreSQL instance to accept ready checks."""

    deadline = datetime.now(timezone.utc).timestamp() + timeout_seconds
    while datetime.now(timezone.utc).timestamp() < deadline:
        ready = subprocess.run(
            ["docker", "exec", container_name, "pg_isready", "-U", user_name, "-d", database_name],
            check=False,
            capture_output=True,
            text=True,
        )
        if ready.returncode == 0:
            return
        time.sleep(1)
    raise AssertionError(f"Timed out waiting for {container_name} to become ready.")


def _run_packaged_migrations(repo_root: Path, dsn: str, *, backup_dir: Path) -> None:
    """Apply packaged migrations to one explicit DSN."""

    backup_dir.mkdir(parents=True, exist_ok=True)
    shellbrain_home = backup_dir.parent / ".shellbrain-home"
    shellbrain_home.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "app.periphery.cli.main", "admin", "migrate"],
        check=True,
        cwd=repo_root,
        env={
            **os.environ,
            "SHELLBRAIN_DB_DSN": dsn,
            "SHELLBRAIN_DB_ADMIN_DSN": dsn,
            "SHELLBRAIN_BACKUP_DIR": str(backup_dir),
            "SHELLBRAIN_HOME": str(shellbrain_home),
            "SHELLBRAIN_INSTANCE_MODE": "test",
        },
        capture_output=True,
        text=True,
    )


def _wait_for_host_postgres(dsn: str, *, timeout_seconds: int = 60) -> None:
    """Wait for one host-routable PostgreSQL DSN to accept client connections."""

    deadline = time.time() + timeout_seconds
    raw_dsn = dsn.replace("+psycopg", "")
    while time.time() < deadline:
        try:
            with psycopg.connect(raw_dsn, connect_timeout=2):
                return
        except psycopg.OperationalError:
            time.sleep(1)
    raise AssertionError(f"Timed out waiting for host PostgreSQL connectivity on {raw_dsn}.")


def _seed_sentinel_dataset(dsn: str) -> dict[str, str]:
    """Seed one representative legacy dataset through the real shellbrain write path."""

    engine = get_engine(dsn)
    session_factory = get_session_factory(engine)

    def _uow_factory() -> PostgresUnitOfWork:
        return PostgresUnitOfWork(session_factory)

    episode_id = f"episode-{uuid4().hex[:8]}"
    event_id = f"event-{uuid4().hex[:8]}"
    memory_text = "Legacy local shellbrain data."
    now = datetime.now(timezone.utc)

    with _uow_factory() as uow:
        uow.episodes.create_episode(
            Episode(
                id=episode_id,
                repo_id="migration-repo",
                host_app="codex",
                thread_id=f"codex:{episode_id}",
                status=EpisodeStatus.ACTIVE,
                started_at=now,
                created_at=now,
            )
        )
        uow.episodes.append_event(
            EpisodeEvent(
                id=event_id,
                episode_id=episode_id,
                seq=1,
                host_event_key=event_id,
                source=EpisodeEventSource.USER,
                content='{"content_kind":"message","content_text":"legacy evidence"}',
                created_at=now,
            )
        )

    result = handle_create(
        {
            "memory": {
                "text": memory_text,
                "kind": "problem",
                "evidence_refs": [event_id],
            }
        },
        uow_factory=_uow_factory,
        embedding_provider_factory=_StubEmbeddingProvider,
        embedding_model="stub-v1",
        inferred_repo_id="migration-repo",
        defaults={"scope": "repo"},
    )
    engine.dispose()

    assert result["status"] == "ok"

    return {
        "memory_id": str(result["data"]["memory_id"]),
        "memory_text": memory_text,
    }


def _fetch_memory_text(dsn: str, memory_id: str) -> str:
    """Fetch one memory row text by id from the target database."""

    with psycopg.connect(dsn.replace("+psycopg", "")) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT text FROM memories WHERE id = %s", (memory_id,))
            row = cur.fetchone()
    assert row is not None
    return str(row[0])


def _list_databases(dsn: str) -> list[str]:
    """List non-template databases visible to the target connection."""

    with psycopg.connect(dsn.replace("+psycopg", "")) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname")
            return [str(row[0]) for row in cur.fetchall()]


def _reserve_tcp_port() -> int:
    """Reserve one localhost TCP port for an isolated PostgreSQL test instance."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])
