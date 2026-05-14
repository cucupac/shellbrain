"""High-level behavior contracts for active-episode event browsing."""

from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path

from tests.operations._shared.handler_calls import handle_events
from app.infrastructure.db.runtime.models.episodes import episode_events
from app.infrastructure.db.runtime.uow import PostgresUnitOfWork


def test_events_syncs_the_resolved_active_session_and_returns_recent_events_newest_first(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    count_rows: Callable[[str], int],
) -> None:
    """events should always sync the active host session and return recent stored events newest first."""

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
    assert result["data"]["host_app"] == "codex"
    assert (
        result["data"]["thread_id"] == codex_transcript_fixture["canonical_thread_id"]
    )
    assert count_rows("episode_events") == 3

    events = result["data"]["events"]
    assert [event["seq"] for event in events] == [3, 2, 1]
    assert [event["source"] for event in events] == ["tool", "assistant", "user"]
    assert events[0]["content"]["content_text"] == "pytest failed"


def test_events_with_episode_id_reads_exact_stored_episode_without_syncing(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    count_rows: Callable[[str], int],
) -> None:
    """events with episode_id should read stored evidence without active-session selection."""

    first_result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="shellbrain",
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={
            "codex": list(codex_transcript_fixture["search_roots"]),
            "claude_code": [],
        },
    )
    episode_id = first_result["data"]["episode_id"]

    result = handle_events(
        {"episode_id": episode_id, "limit": 2},
        uow_factory=uow_factory,
        inferred_repo_id="shellbrain",
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={"codex": [], "claude_code": [], "cursor": []},
    )

    assert result["status"] == "ok"
    assert result["data"]["episode_id"] == episode_id
    assert [event["seq"] for event in result["data"]["events"]] == [3, 2]
    assert count_rows("episode_events") == 3


def test_events_with_episode_range_returns_all_matching_events_oldest_first(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
) -> None:
    """exact event ranges should cover (after_seq, up_to_seq] deterministically."""

    first_result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="shellbrain",
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={
            "codex": list(codex_transcript_fixture["search_roots"]),
            "claude_code": [],
        },
    )
    episode_id = first_result["data"]["episode_id"]

    result = handle_events(
        {"episode_id": episode_id, "after_seq": 1, "up_to_seq": 3},
        uow_factory=uow_factory,
        inferred_repo_id="shellbrain",
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={"codex": [], "claude_code": [], "cursor": []},
    )

    assert result["status"] == "ok"
    assert [event["seq"] for event in result["data"]["events"]] == [2, 3]
    assert result["data"]["event_range"] == {
        "after_seq": 1,
        "up_to_seq": 3,
        "order": "oldest_first",
        "returned_count": 2,
        "expected_count": 2,
        "complete": True,
    }


def test_events_selects_the_most_recent_matching_host_session_across_supported_hosts(
    codex_transcript_fixture: dict[str, object],
    claude_code_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
    monkeypatch,
) -> None:
    """events should always prefer the trusted caller identity over newer repo-matching host sessions."""

    codex_path = Path(str(codex_transcript_fixture["transcript_path"]))
    claude_path = Path(str(claude_code_transcript_fixture["transcript_path"]))
    os.utime(codex_path, (codex_path.stat().st_atime, codex_path.stat().st_mtime - 10))
    os.utime(claude_path, None)
    monkeypatch.setenv(
        "CODEX_THREAD_ID", str(codex_transcript_fixture["host_session_key"])
    )

    result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="shellbrain",
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={
            "codex": list(codex_transcript_fixture["search_roots"]),
            "claude_code": list(claude_code_transcript_fixture["search_roots"]),
        },
    )

    assert result["status"] == "ok"
    assert result["data"]["host_app"] == "codex"
    assert (
        result["data"]["thread_id"] == codex_transcript_fixture["canonical_thread_id"]
    )

    rows = fetch_rows(episode_events)
    assert len(rows) == 3


def test_events_should_fall_back_to_cursor_when_no_trusted_host_exists(
    cursor_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
) -> None:
    """events should sync a repo-matching Cursor composer when no trusted host overrides it."""

    result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="shellbrain",
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={
            "codex": [],
            "claude_code": [],
            "cursor": list(cursor_transcript_fixture["search_roots"]),
        },
    )

    assert result["status"] == "ok"
    assert result["data"]["host_app"] == "cursor"
    assert (
        result["data"]["thread_id"] == cursor_transcript_fixture["canonical_thread_id"]
    )


def test_events_should_keep_trusted_codex_over_a_newer_cursor_candidate(
    codex_transcript_fixture: dict[str, object],
    cursor_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    monkeypatch,
) -> None:
    """trusted caller identity should still win even when Cursor has the newer fallback candidate."""

    monkeypatch.setenv(
        "CODEX_THREAD_ID", str(codex_transcript_fixture["host_session_key"])
    )

    result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="shellbrain",
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={
            "codex": list(codex_transcript_fixture["search_roots"]),
            "claude_code": [],
            "cursor": list(cursor_transcript_fixture["search_roots"]),
        },
    )

    assert result["status"] == "ok"
    assert result["data"]["host_app"] == "codex"
    assert (
        result["data"]["thread_id"] == codex_transcript_fixture["canonical_thread_id"]
    )
