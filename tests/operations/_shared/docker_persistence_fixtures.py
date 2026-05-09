"""Shared Docker-backed persistence fixtures for destructive durability tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from typing import Callable
from uuid import uuid4

import psycopg
import pytest
from sqlalchemy import select

from app.core.entities.episodes import (
    Episode,
    EpisodeEvent,
    EpisodeEventSource,
    EpisodeStatus,
)
from app.core.ports.embeddings.provider import IEmbeddingProvider
from tests.operations._shared.handler_calls import handle_memory_add
from app.infrastructure.db.runtime.engine import get_engine
from app.infrastructure.db.runtime.models.evidence import evidence_refs
from app.infrastructure.db.runtime.models.episodes import episode_events, episodes
from app.infrastructure.db.runtime.models.memories import (
    memories,
    memory_embeddings,
    memory_evidence,
)
from app.infrastructure.db.runtime.session import get_session_factory
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork


_READY_TIMEOUT_SECONDS = 60
_SENTINEL_REPO_ID = "persistence-repo"
_SENTINEL_TEXT = "Persistence sentinel memory."


class _StubEmbeddingProvider(IEmbeddingProvider):
    """Deterministic embedding provider used by Docker-backed persistence tests."""

    def embed(self, text: str) -> list[float]:
        """Return one stable vector for any input text."""

        _ = text
        return [0.1, 0.2, 0.3, 0.4]


@dataclass(frozen=True)
class SentinelDataset:
    """Expected sentinel rows used to verify persistence and restore behavior."""

    repo_id: str
    episode_id: str
    thread_id: str
    event_id: str
    memory_id: str | None = None
    memory_text: str = _SENTINEL_TEXT


class IsolatedDockerPostgres:
    """Manage one isolated Docker Compose PostgreSQL environment for persistence tests."""

    def __init__(
        self, *, repo_root: Path, base_dir: Path, label: str, test_name: str
    ) -> None:
        self.repo_root = repo_root
        self.base_dir = base_dir
        self.label = label
        self.test_name = test_name
        self.identifier = uuid4().hex[:8]
        safe_test_name = _slugify(test_name)[:24]
        self.project_name = f"shellbrain-{safe_test_name}-{label}-{self.identifier}"
        self.container_name = f"{self.project_name}-postgres"
        self.port = _reserve_tcp_port()
        self.db_name = f"shellbrain_{self.identifier}"
        self.user = f"shellbrain_{self.identifier}"
        self.password = f"shellbrain_{self.identifier}"
        self.data_dir = self.base_dir / "postgres-data"
        self.dump_dir = self.base_dir / "dump"
        self.shellbrain_home = self.base_dir / ".shellbrain-home"
        self._engine = None
        self._session_factory = None
        self._sentinel = SentinelDataset(
            repo_id=_SENTINEL_REPO_ID,
            episode_id=f"episode-{self.identifier}",
            thread_id=f"codex:persistence-{self.identifier}",
            event_id=f"event-{self.identifier}",
        )

    @property
    def dsn(self) -> str:
        """Return SQLAlchemy DSN for this isolated database."""

        return f"postgresql+psycopg://{self.user}:{self.password}@127.0.0.1:{self.port}/{self.db_name}"

    @property
    def raw_dsn(self) -> str:
        """Return psycopg-compatible DSN for this isolated database."""

        return self.dsn.replace("+psycopg", "")

    @property
    def sentinel(self) -> SentinelDataset:
        """Return the most recently seeded sentinel dataset for this environment."""

        return self._sentinel

    def start_isolated_db(self) -> None:
        """Bring up the isolated PostgreSQL service and bind fresh client runtime state."""

        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.dump_dir.mkdir(parents=True, exist_ok=True)
        self._run_compose("up", "-d", "db")
        self._wait_for_db()
        self._rebind_runtime()

    def run_migrations(self) -> None:
        """Apply packaged schema migrations against the isolated database."""

        self._run_repo_command(
            [
                _resolve_python_executable(),
                "-m",
                "app.entrypoints.cli.main",
                "admin",
                "migrate",
            ],
            env_overrides={
                "SHELLBRAIN_DB_DSN": self.dsn,
                "SHELLBRAIN_DB_ADMIN_DSN": self.dsn,
                "SHELLBRAIN_HOME": str(self.shellbrain_home),
                "SHELLBRAIN_INSTANCE_MODE": "test",
            },
        )
        self._rebind_runtime()

    def destroy_db_container(self) -> None:
        """Remove only the isolated database container while preserving host-mounted data."""

        self._dispose_runtime()
        self._run_compose("rm", "-sf", "db")

    def recreate_db_container(self) -> None:
        """Recreate the isolated database container on the existing host-mounted data path."""

        self.start_isolated_db()

    def dump_db(self, dump_path: Path) -> Path:
        """Write a logical SQL backup for this isolated database to a host file."""

        dump_path.parent.mkdir(parents=True, exist_ok=True)
        with dump_path.open("w", encoding="utf-8") as handle:
            self._run_host_command(
                [
                    "docker",
                    "exec",
                    "-i",
                    self.container_name,
                    "sh",
                    "-lc",
                    'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
                ],
                stdout=handle,
            )
        return dump_path

    def restore_db(self, dump_path: Path) -> None:
        """Restore one logical SQL backup into this isolated database."""

        with dump_path.open("r", encoding="utf-8") as handle:
            self._run_host_command(
                [
                    "docker",
                    "exec",
                    "-i",
                    self.container_name,
                    "sh",
                    "-lc",
                    'PGPASSWORD="$POSTGRES_PASSWORD" psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
                ],
                stdin=handle,
            )
        self._rebind_runtime()

    def seed_sentinel_dataset(self) -> SentinelDataset:
        """Seed one representative episode/event/shellbrain dataset through the real shellbrain system."""

        now = datetime.now(timezone.utc)
        with self.make_uow_factory()() as uow:
            uow.episodes.create_episode(
                Episode(
                    id=self._sentinel.episode_id,
                    repo_id=self._sentinel.repo_id,
                    host_app="codex",
                    thread_id=self._sentinel.thread_id,
                    status=EpisodeStatus.ACTIVE,
                    started_at=now,
                    created_at=now,
                )
            )
            uow.episodes.append_event(
                EpisodeEvent(
                    id=self._sentinel.event_id,
                    episode_id=self._sentinel.episode_id,
                    seq=1,
                    host_event_key=self._sentinel.event_id,
                    source=EpisodeEventSource.USER,
                    content='{"content_kind":"message","content_text":"persistence evidence"}',
                    created_at=now,
                )
            )

        result = handle_memory_add(
            {
                "memory": {
                    "text": self._sentinel.memory_text,
                    "kind": "problem",
                    "evidence_refs": [self._sentinel.event_id],
                }
            },
            uow_factory=self.make_uow_factory(),
            embedding_provider_factory=_StubEmbeddingProvider,
            embedding_model="stub-v1",
            inferred_repo_id=self._sentinel.repo_id,
            defaults={"scope": "repo"},
        )
        if result.get("status") != "ok":
            raise AssertionError(f"Failed to seed sentinel dataset: {result}")

        self._sentinel = SentinelDataset(
            repo_id=self._sentinel.repo_id,
            episode_id=self._sentinel.episode_id,
            thread_id=self._sentinel.thread_id,
            event_id=self._sentinel.event_id,
            memory_id=str(result["data"]["memory_id"]),
            memory_text=self._sentinel.memory_text,
        )
        return self._sentinel

    def assert_sentinel_dataset(self, expected: SentinelDataset | None = None) -> None:
        """Assert that the sentinel dataset exists with intact cross-table links."""

        expected = expected or self._sentinel
        if expected.memory_id is None:
            raise AssertionError("Sentinel dataset has not been seeded yet.")
        if self._engine is None:
            raise AssertionError("Database runtime is not bound.")

        with self._engine.connect() as conn:
            episode_rows = conn.execute(select(episodes)).mappings().all()
            event_rows = conn.execute(select(episode_events)).mappings().all()
            memory_rows = conn.execute(select(memories)).mappings().all()
            embedding_rows = conn.execute(select(memory_embeddings)).mappings().all()
            evidence_rows = conn.execute(select(evidence_refs)).mappings().all()
            memory_evidence_rows = (
                conn.execute(select(memory_evidence)).mappings().all()
            )

        assert len(episode_rows) == 1
        assert len(event_rows) == 1
        assert len(memory_rows) == 1
        assert len(embedding_rows) == 1
        assert len(evidence_rows) == 1
        assert len(memory_evidence_rows) == 1

        episode_row = episode_rows[0]
        assert episode_row["id"] == expected.episode_id
        assert episode_row["repo_id"] == expected.repo_id
        assert episode_row["thread_id"] == expected.thread_id

        event_row = event_rows[0]
        assert event_row["id"] == expected.event_id
        assert event_row["episode_id"] == expected.episode_id
        assert event_row["host_event_key"] == expected.event_id

        memory_row = memory_rows[0]
        assert memory_row["id"] == expected.memory_id
        assert memory_row["repo_id"] == expected.repo_id
        assert memory_row["text"] == expected.memory_text
        assert memory_row["kind"] == "problem"
        assert memory_row["scope"] == "repo"

        embedding_row = embedding_rows[0]
        assert embedding_row["memory_id"] == expected.memory_id
        assert embedding_row["model"] == "stub-v1"
        assert embedding_row["dim"] == 4

        evidence_row = evidence_rows[0]
        assert evidence_row["repo_id"] == expected.repo_id
        assert evidence_row["ref"] == expected.event_id
        assert evidence_row["episode_event_id"] == expected.event_id

        memory_evidence_row = memory_evidence_rows[0]
        assert memory_evidence_row["memory_id"] == expected.memory_id
        assert memory_evidence_row["evidence_id"] == evidence_row["id"]

    def make_uow_factory(self) -> Callable[[], PostgresUnitOfWork]:
        """Return a fresh unit-of-work factory bound to the current isolated database."""

        if self._session_factory is None:
            raise RuntimeError(
                "Call start_isolated_db() before creating a unit-of-work factory."
            )

        def _factory() -> PostgresUnitOfWork:
            return PostgresUnitOfWork(self._session_factory)

        return _factory

    def cleanup(self) -> None:
        """Remove isolated Docker resources and temp files for this environment."""

        self._dispose_runtime()
        try:
            self._run_compose("down", "--remove-orphans", "--timeout", "5")
        except RuntimeError:
            pass
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def _rebind_runtime(self) -> None:
        """Create a fresh SQLAlchemy engine/session factory for the current database process."""

        self._dispose_runtime()
        self._engine = get_engine(self.dsn)
        self._session_factory = get_session_factory(self._engine)

    def _dispose_runtime(self) -> None:
        """Dispose any currently bound SQLAlchemy runtime state."""

        if self._engine is not None:
            self._engine.dispose()
        self._engine = None
        self._session_factory = None

    def _wait_for_db(self) -> None:
        """Wait until the isolated database accepts new psycopg connections."""

        deadline = time.monotonic() + _READY_TIMEOUT_SECONDS
        while True:
            try:
                with psycopg.connect(self.raw_dsn, connect_timeout=2):
                    return
            except Exception as exc:
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"Timed out waiting for isolated database '{self.project_name}' to become ready."
                    ) from exc
                time.sleep(1)

    def _run_compose(self, *args: str) -> str:
        """Run one docker compose command scoped to this isolated project."""

        return self._run_repo_command(
            ["docker", "compose", "-p", self.project_name, *args],
            env_overrides=self._compose_env(),
        )

    def _run_repo_command(
        self,
        command: list[str],
        *,
        env_overrides: dict[str, str] | None = None,
    ) -> str:
        """Run one host command from the repository root and return stdout."""

        env = dict(os.environ)
        if env_overrides:
            env.update(env_overrides)
        try:
            completed = subprocess.run(
                command,
                check=True,
                cwd=self.repo_root,
                env=env,
                text=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Command failed: {' '.join(command)}\nSTDOUT:\n{exc.stdout}\nSTDERR:\n{exc.stderr}"
            ) from exc
        return completed.stdout

    def _run_host_command(
        self,
        command: list[str],
        *,
        stdin=None,
        stdout=None,
    ) -> None:
        """Run one host command and surface stderr on failure."""

        try:
            subprocess.run(
                command,
                check=True,
                cwd=self.repo_root,
                stdin=stdin,
                stdout=stdout,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Command failed: {' '.join(command)}\nSTDERR:\n{exc.stderr}"
            ) from exc

    def _compose_env(self) -> dict[str, str]:
        """Return docker compose environment variables for this isolated project."""

        return {
            "POSTGRES_DB": self.db_name,
            "POSTGRES_USER": self.user,
            "POSTGRES_PASSWORD": self.password,
            "POSTGRES_PORT": str(self.port),
            "SHELLBRAIN_DB_DATA_DIR": str(self.data_dir),
            "SHELLBRAIN_DB_CONTAINER_NAME": self.container_name,
        }


def _ensure_docker_available() -> None:
    """Fail fast when Docker or Docker Compose are unavailable."""

    for command in (["docker", "version"], ["docker", "compose", "version"]):
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise RuntimeError(
                "Docker and Docker Compose are required for persistence tests."
            ) from exc


def _reserve_tcp_port() -> int:
    """Reserve one ephemeral host TCP port for an isolated PostgreSQL instance."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _slugify(value: str) -> str:
    """Convert one arbitrary pytest node name into a Docker-safe slug."""

    sanitized = [
        character.lower() if character.isalnum() else "-" for character in value
    ]
    slug = "".join(sanitized).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "test"


def _resolve_python_executable() -> str:
    """Resolve the Python executable used to launch packaged admin commands."""

    return sys.executable


@pytest.fixture
def isolated_db_factory(tmp_path: Path, request: pytest.FixtureRequest):
    """Create isolated Docker-backed PostgreSQL environments and clean them up reliably."""

    _ensure_docker_available()
    environments: list[IsolatedDockerPostgres] = []

    def _factory(label: str) -> IsolatedDockerPostgres:
        environment = IsolatedDockerPostgres(
            repo_root=Path(__file__).resolve().parents[3],
            base_dir=tmp_path / label,
            label=label,
            test_name=request.node.name,
        )
        environments.append(environment)
        return environment

    yield _factory

    for environment in reversed(environments):
        environment.cleanup()
