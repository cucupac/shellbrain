"""Record-write contracts for episode-sync telemetry."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from app.periphery.cli.handlers import handle_events
from app.periphery.db.uow import PostgresUnitOfWork
from app.periphery.episodes.poller import run_episode_poller

pytestmark = pytest.mark.usefixtures("telemetry_db_reset")


class _NoOpLock:
    """Minimal lock-handle test double that satisfies the poller release contract."""

    def release(self) -> None:
        """Release nothing."""

        return None


def test_events_should_always_append_one_episode_sync_run_for_inline_transcript_sync(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """events should always append one episode sync run for inline transcript sync."""

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

    assert result["status"] == "ok"
    assert_relation_exists("episode_sync_runs")
    rows = fetch_relation_rows("episode_sync_runs", order_by="created_at DESC, id DESC")

    assert len(rows) == 1
    assert rows[0]["source"] == "events_inline"
    assert rows[0]["repo_id"] == "shellbrain"


def test_poller_sync_should_always_append_one_episode_sync_run_with_source_poller(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """poller sync should always append one episode sync run with source poller."""

    monkeypatch.setattr("app.periphery.episodes.poller.get_uow_factory", lambda: uow_factory)
    monkeypatch.setattr("app.periphery.episodes.poller.acquire_poller_lock", lambda **kwargs: _NoOpLock())
    monkeypatch.setattr("app.periphery.episodes.poller.write_poller_pid_artifact", lambda **kwargs: Path("/tmp/episode_sync.pid"))
    monkeypatch.setattr("app.periphery.episodes.poller.POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr("app.periphery.episodes.poller.IDLE_EXIT_SECONDS", 0)
    monkeypatch.setattr(
        "app.periphery.episodes.poller.default_search_roots",
        lambda *, repo_root, host_app: list(codex_transcript_fixture["search_roots"]) if host_app == "codex" else [],
    )

    run_episode_poller(repo_id="shellbrain", repo_root=Path.cwd().resolve())

    assert_relation_exists("episode_sync_runs")
    rows = fetch_relation_rows("episode_sync_runs", order_by="created_at DESC, id DESC")

    assert len(rows) == 1
    assert rows[0]["source"] == "poller"
    assert rows[0]["repo_id"] == "shellbrain"


def test_poller_with_an_active_lock_should_not_append_episode_sync_runs(
    tmp_path: Path,
    assert_relation_exists,
    fetch_relation_rows,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """poller with an active lock should always exit without writing telemetry."""

    monkeypatch.setattr("app.periphery.episodes.poller.acquire_poller_lock", lambda **kwargs: None)

    run_episode_poller(repo_id="shellbrain", repo_root=tmp_path / "repo")

    assert_relation_exists("episode_sync_runs")
    assert fetch_relation_rows("episode_sync_runs") == []


def test_episode_sync_runs_should_always_record_imported_event_count_and_total_event_counts_by_source(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """episode sync runs should always record imported-event count and total event counts by source."""

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

    assert result["status"] == "ok"
    assert_relation_exists("episode_sync_runs")
    rows = fetch_relation_rows("episode_sync_runs", order_by="created_at DESC, id DESC")

    assert len(rows) == 1
    row = rows[0]
    assert row["imported_event_count"] == 3
    assert row["total_event_count"] == 3
    assert row["user_event_count"] == 1
    assert row["assistant_event_count"] == 1
    assert row["tool_event_count"] == 1


def test_episode_sync_runs_should_always_record_tool_type_counts_from_the_normalized_episode_content(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """episode sync runs should always record tool-type counts from the normalized episode content."""

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

    assert result["status"] == "ok"
    assert_relation_exists("episode_sync_tool_types")
    rows = fetch_relation_rows("episode_sync_tool_types", order_by="sync_run_id ASC, tool_type ASC")

    assert len(rows) == 1
    assert rows[0]["tool_type"] == "exec_command"
    assert rows[0]["event_count"] == 1
