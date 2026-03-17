"""High-level behavior contracts for active-episode event browsing."""

from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path

from shellbrain.periphery.cli.handlers import handle_events
from shellbrain.periphery.db.models.episodes import episode_events
from shellbrain.periphery.db.uow import PostgresUnitOfWork


def test_events_syncs_the_resolved_active_session_and_returns_recent_events_newest_first(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    count_rows: Callable[[str], int],
) -> None:
    """events should always sync the active host session and return recent stored events newest first."""

    result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="memory",
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={
            "codex": list(codex_transcript_fixture["search_roots"]),
            "claude_code": [],
        },
    )

    assert result["status"] == "ok"
    assert result["data"]["host_app"] == "codex"
    assert result["data"]["thread_id"] == codex_transcript_fixture["canonical_thread_id"]
    assert count_rows("episode_events") == 3

    events = result["data"]["events"]
    assert [event["seq"] for event in events] == [3, 2, 1]
    assert [event["source"] for event in events] == ["tool", "assistant", "user"]
    assert events[0]["content"]["content_text"] == "pytest failed"


def test_events_selects_the_most_recent_matching_host_session_across_supported_hosts(
    codex_transcript_fixture: dict[str, object],
    claude_code_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    fetch_rows: Callable[..., list[dict[str, object]]],
) -> None:
    """events should always select the most recently updated matching host session across supported hosts."""

    codex_path = Path(str(codex_transcript_fixture["transcript_path"]))
    claude_path = Path(str(claude_code_transcript_fixture["transcript_path"]))
    os.utime(codex_path, (codex_path.stat().st_atime, codex_path.stat().st_mtime - 10))
    os.utime(claude_path, None)

    result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="memory",
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={
            "codex": list(codex_transcript_fixture["search_roots"]),
            "claude_code": list(claude_code_transcript_fixture["search_roots"]),
        },
    )

    assert result["status"] == "ok"
    assert result["data"]["host_app"] == "claude_code"
    assert result["data"]["thread_id"] == claude_code_transcript_fixture["canonical_thread_id"]

    rows = fetch_rows(episode_events)
    assert len(rows) == 3
