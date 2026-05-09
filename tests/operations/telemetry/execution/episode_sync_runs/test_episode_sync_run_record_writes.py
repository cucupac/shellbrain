"""Record-write contracts for episode-sync telemetry."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import nullcontext
import os
from pathlib import Path

import pytest

from tests.operations._shared.handler_calls import handle_events
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork
from app.infrastructure.process.episode_sync.poller import run_episode_poller

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

    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.acquire_poller_lock",
        lambda **kwargs: _NoOpLock(),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.write_poller_pid_artifact",
        lambda **kwargs: Path("/tmp/episode_sync.pid"),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.POLL_INTERVAL_SECONDS", 0
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.IDLE_EXIT_SECONDS", 0
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.default_search_roots",
        lambda *, repo_root, host_app: (
            list(codex_transcript_fixture["search_roots"])
            if host_app == "codex"
            else []
        ),
    )

    run_episode_poller(
        repo_id="shellbrain", repo_root=Path.cwd().resolve(), uow_factory=uow_factory
    )

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

    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.acquire_poller_lock",
        lambda **kwargs: None,
    )

    run_episode_poller(
        repo_id="shellbrain",
        repo_root=tmp_path / "repo",
        uow_factory=lambda: nullcontext(object()),
    )

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
    rows = fetch_relation_rows(
        "episode_sync_tool_types", order_by="sync_run_id ASC, tool_type ASC"
    )

    assert len(rows) == 1
    assert rows[0]["tool_type"] == "exec_command"
    assert rows[0]["event_count"] == 1


def test_events_should_always_append_model_usage_rows_for_inline_sync(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """events should always persist normalized model usage after inline transcript sync."""

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
    assert_relation_exists("model_usage")
    rows = fetch_relation_rows(
        "model_usage", order_by="occurred_at ASC, host_usage_key ASC"
    )

    assert len(rows) == 1
    assert rows[0]["repo_id"] == "shellbrain"
    assert rows[0]["host_app"] == "codex"
    assert rows[0]["input_tokens"] == 1200
    assert rows[0]["output_tokens"] == 90
    assert rows[0]["cached_input_tokens_total"] == 300
    assert rows[0]["reasoning_output_tokens"] == 25


def test_poller_should_use_candidate_updated_at_instead_of_shared_db_mtime_for_cursor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cursor poller freshness should track the composer marker, not the shared DB mtime."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cursor_root = tmp_path / "Cursor" / "User"
    transcript_path = cursor_root / "globalStorage" / "state.vscdb"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text("stub", encoding="utf-8")
    os.utime(transcript_path, (10.0, 10.0))

    sync_calls: list[dict[str, object]] = []
    discovery_calls = {"cursor": 0}

    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.acquire_poller_lock",
        lambda **kwargs: _NoOpLock(),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.write_poller_pid_artifact",
        lambda **kwargs: Path("/tmp/episode_sync.pid"),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller._record_sync_telemetry_best_effort",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller._close_episode",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.POLL_INTERVAL_SECONDS", 0
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.IDLE_EXIT_SECONDS", 0
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.default_search_roots",
        lambda *, repo_root, host_app: [cursor_root] if host_app == "cursor" else [],
    )

    def _discover_active_host_session(*, host_app, repo_root, search_roots):
        if host_app != "cursor":
            return None
        discovery_calls["cursor"] += 1
        if discovery_calls["cursor"] == 2:
            os.utime(transcript_path, (20.0, 20.0))
        return {
            "host_app": "cursor",
            "host_session_key": "cursor-composer-1",
            "transcript_path": transcript_path,
            "updated_at": 1234.0,
        }

    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.discover_active_host_session",
        _discover_active_host_session,
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.sync_episode_from_host",
        lambda **kwargs: (
            sync_calls.append(kwargs)
            or {
                "thread_id": "cursor:cursor-composer-1",
                "episode_id": "ep-1",
                "transcript_path": str(transcript_path),
                "imported_event_count": 0,
                "total_event_count": 0,
                "user_event_count": 0,
                "assistant_event_count": 0,
                "tool_event_count": 0,
                "system_event_count": 0,
                "tool_type_counts": {},
            }
        ),
    )

    run_episode_poller(
        repo_id="shellbrain",
        repo_root=repo_root,
        uow_factory=lambda: nullcontext(object()),
    )

    assert discovery_calls["cursor"] >= 2
    assert len(sync_calls) == 1
    assert sync_calls[0]["host_app"] == "cursor"


def test_poller_sync_should_always_append_model_usage_rows(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch: pytest.MonkeyPatch,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """poller sync should always persist normalized model usage rows."""

    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.acquire_poller_lock",
        lambda **kwargs: _NoOpLock(),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.write_poller_pid_artifact",
        lambda **kwargs: Path("/tmp/episode_sync.pid"),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.POLL_INTERVAL_SECONDS", 0
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.IDLE_EXIT_SECONDS", 0
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.default_search_roots",
        lambda *, repo_root, host_app: (
            list(codex_transcript_fixture["search_roots"])
            if host_app == "codex"
            else []
        ),
    )

    run_episode_poller(
        repo_id="shellbrain", repo_root=Path.cwd().resolve(), uow_factory=uow_factory
    )

    assert_relation_exists("model_usage")
    rows = fetch_relation_rows(
        "model_usage", order_by="occurred_at ASC, host_usage_key ASC"
    )

    assert len(rows) == 1
    assert rows[0]["host_app"] == "codex"
    assert rows[0]["source_kind"] == "codex_transcript"
