"""Failure-handling contracts for telemetry writes on unsuccessful operations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.operations._shared.handler_calls import (
    handle_memory_add,
    handle_events,
    handle_read,
    handle_update,
)
from app.infrastructure.db.uow import PostgresUnitOfWork
from app.infrastructure.process.episode_poller import run_episode_poller

pytestmark = pytest.mark.usefixtures("telemetry_db_reset")


class _NoOpLock:
    """Minimal lock-handle test double that satisfies the poller release contract."""

    def release(self) -> None:
        """Release nothing."""

        return None


def test_read_validation_failures_should_always_append_one_failed_operation_invocation_and_no_read_summary_row(
    uow_factory: Callable[[], PostgresUnitOfWork],
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """read validation failures should always append one failed operation invocation and no read summary row."""

    result = handle_read(
        {"mode": "targeted"},
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "error"
    assert_relation_exists("operation_invocations")
    invocation_rows = fetch_relation_rows(
        "operation_invocations",
        where_sql="command = :command",
        params={"command": "read"},
    )
    read_summary_rows = fetch_relation_rows("read_invocation_summaries")

    assert len(invocation_rows) == 1
    assert invocation_rows[0]["outcome"] == "error"
    assert read_summary_rows == []


def test_create_validation_failures_should_always_append_one_failed_operation_invocation_and_no_write_summary_row(
    uow_factory: Callable[[], PostgresUnitOfWork],
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """create validation failures should always append one failed operation invocation and no write summary row."""

    result = handle_memory_add(
        {
            "memory": {
                "text": "Invalid solution payload.",
                "scope": "repo",
                "kind": "solution",
                "evidence_refs": ["session://1"],
            }
        },
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: None,
        embedding_model="stub-v1",
        inferred_repo_id="repo-a",
        defaults={"scope": "repo"},
    )

    assert result["status"] == "error"
    assert_relation_exists("operation_invocations")
    invocation_rows = fetch_relation_rows(
        "operation_invocations",
        where_sql="command = :command",
        params={"command": "create"},
    )
    write_rows = fetch_relation_rows("write_invocation_summaries")

    assert len(invocation_rows) == 1
    assert invocation_rows[0]["outcome"] == "error"
    assert write_rows == []


def test_update_validation_failures_should_always_append_one_failed_operation_invocation_and_no_write_summary_row(
    uow_factory: Callable[[], PostgresUnitOfWork],
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """update validation failures should always append one failed operation invocation and no write summary row."""

    result = handle_update(
        {
            "update": {
                "type": "archive_state",
                "archived": True,
            }
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "error"
    assert_relation_exists("operation_invocations")
    invocation_rows = fetch_relation_rows(
        "operation_invocations",
        where_sql="command = :command",
        params={"command": "update"},
    )
    write_rows = fetch_relation_rows("write_invocation_summaries")

    assert len(invocation_rows) == 1
    assert invocation_rows[0]["outcome"] == "error"
    assert write_rows == []


def test_events_not_found_should_always_append_one_failed_operation_invocation_and_no_episode_sync_run(
    tmp_path: Path,
    uow_factory: Callable[[], PostgresUnitOfWork],
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """events not_found should always append one failed operation invocation and no episode sync run."""

    result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="shellbrain",
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={
            "codex": [tmp_path / "missing-codex-root"],
            "claude_code": [tmp_path / "missing-claude-root"],
        },
    )

    assert result["status"] == "error"
    assert_relation_exists("operation_invocations")
    invocation_rows = fetch_relation_rows(
        "operation_invocations",
        where_sql="command = :command",
        params={"command": "events"},
    )
    sync_rows = fetch_relation_rows("episode_sync_runs")

    assert len(invocation_rows) == 1
    assert invocation_rows[0]["outcome"] == "error"
    assert sync_rows == []


def test_events_sync_failures_should_always_append_one_failed_operation_invocation_and_one_failed_episode_sync_run(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """events sync failures should always append one failed operation invocation and one failed episode sync run."""

    monkeypatch.setattr(
        "app.startup.cli_handlers.normalize_host_transcript",
        lambda **kwargs: (_ for _ in ()).throw(FileNotFoundError("missing transcript")),
    )

    result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="shellbrain",
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={
            "codex": list(codex_transcript_fixture["search_roots"]),
            "claude_code": [],
        },
    )

    assert result["status"] == "error"
    assert_relation_exists("operation_invocations")
    invocation_rows = fetch_relation_rows(
        "operation_invocations",
        where_sql="command = :command",
        params={"command": "events"},
    )
    sync_rows = fetch_relation_rows("episode_sync_runs")

    assert len(invocation_rows) == 1
    assert invocation_rows[0]["outcome"] == "error"
    assert sync_rows[0]["outcome"] == "error"


def test_unexpected_operational_failures_should_always_append_one_failed_operation_invocation_with_internal_error_stage(
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """unexpected operational failures should always append one failed operation invocation with internal-error stage."""

    monkeypatch.setattr(
        "app.entrypoints.cli.handlers.internal_agent.retrieval.execution.execute_read_memory",
        lambda request, uow, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    result = handle_read(
        {"query": "internal failure telemetry", "mode": "targeted"},
        uow_factory=uow_factory,
        inferred_repo_id="repo-a",
    )

    assert result["status"] == "error"
    assert_relation_exists("operation_invocations")
    rows = fetch_relation_rows(
        "operation_invocations",
        where_sql="command = :command",
        params={"command": "read"},
    )

    assert len(rows) == 1
    assert rows[0]["outcome"] == "error"
    assert rows[0]["error_stage"] == "internal_error"


def test_poller_sync_failures_should_always_append_one_failed_episode_sync_run(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """poller sync failures should always append one failed episode sync run."""

    monkeypatch.setattr(
        "app.infrastructure.process.episode_poller.acquire_poller_lock",
        lambda **kwargs: _NoOpLock(),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_poller.write_poller_pid_artifact",
        lambda **kwargs: Path("/tmp/episode_sync.pid"),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_poller.POLL_INTERVAL_SECONDS", 0
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_poller.IDLE_EXIT_SECONDS", 0
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_poller.default_search_roots",
        lambda *, repo_root, host_app: (
            list(codex_transcript_fixture["search_roots"])
            if host_app == "codex"
            else []
        ),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_poller.sync_episode_from_host",
        lambda **kwargs: (_ for _ in ()).throw(FileNotFoundError("missing transcript")),
    )

    run_episode_poller(
        repo_id="shellbrain", repo_root=Path.cwd().resolve(), uow_factory=uow_factory
    )

    assert_relation_exists("episode_sync_runs")
    rows = fetch_relation_rows("episode_sync_runs")

    assert len(rows) == 1
    assert rows[0]["outcome"] == "error"
