"""Source-discovery contracts for episodic host transcripts."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.infrastructure.host_apps.transcripts.cursor import list_cursor_sessions_for_repo
from app.infrastructure.host_apps.transcripts.source_discovery import (
    resolve_host_transcript_source,
)


def test_codex_source_resolution_finds_rollout_transcript_from_thread_id(
    codex_transcript_fixture: dict[str, object],
) -> None:
    """codex source resolution should always find a rollout transcript from a thread id."""

    resolved = resolve_host_transcript_source(
        host_app="codex",
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        search_roots=list(codex_transcript_fixture["search_roots"]),
    )

    assert resolved == codex_transcript_fixture["transcript_path"]


def test_claude_code_source_resolution_finds_transcript_from_local_session_metadata(
    claude_code_transcript_fixture: dict[str, object],
) -> None:
    """claude code source resolution should always find a transcript from local session metadata."""

    resolved = resolve_host_transcript_source(
        host_app="claude_code",
        host_session_key=str(claude_code_transcript_fixture["host_session_key"]),
        search_roots=list(claude_code_transcript_fixture["search_roots"]),
    )

    assert resolved == claude_code_transcript_fixture["transcript_path"]


def test_source_resolution_recovers_when_transcript_moved_within_known_host_roots(
    codex_transcript_fixture: dict[str, object],
) -> None:
    """source resolution should always recover when the transcript moved within known host roots."""

    original_path = Path(str(codex_transcript_fixture["transcript_path"]))
    moved_path = original_path.parents[3] / "archive" / original_path.name
    moved_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.rename(moved_path)

    resolved = resolve_host_transcript_source(
        host_app="codex",
        host_session_key=str(codex_transcript_fixture["host_session_key"]),
        search_roots=list(codex_transcript_fixture["search_roots"]),
        last_known_path=original_path,
    )

    assert resolved == moved_path


def test_cursor_source_resolution_returns_the_global_state_db_for_one_active_composer(
    cursor_transcript_fixture: dict[str, object],
) -> None:
    """cursor source resolution should return the shared global DB for the requested composer."""

    resolved = resolve_host_transcript_source(
        host_app="cursor",
        host_session_key=str(cursor_transcript_fixture["host_session_key"]),
        search_roots=list(cursor_transcript_fixture["search_roots"]),
    )

    assert resolved == cursor_transcript_fixture["transcript_path"]


def test_cursor_session_listing_finds_the_active_repo_matching_composer(
    cursor_transcript_fixture: dict[str, object],
) -> None:
    """cursor session discovery should only use active repo-matching composers."""

    candidates = list_cursor_sessions_for_repo(
        repo_root=Path.cwd().resolve(),
        search_roots=list(cursor_transcript_fixture["search_roots"]),
    )

    assert len(candidates) == 1
    assert candidates[0]["host_app"] == "cursor"
    assert (
        candidates[0]["host_session_key"]
        == cursor_transcript_fixture["host_session_key"]
    )
    assert (
        candidates[0]["transcript_path"] == cursor_transcript_fixture["transcript_path"]
    )


def test_source_resolution_fails_clearly_when_host_transcript_can_no_longer_be_found(
    tmp_path: Path,
) -> None:
    """source resolution should always fail clearly when the host transcript can no longer be found."""

    with pytest.raises(FileNotFoundError, match="codex|Codex"):
        resolve_host_transcript_source(
            host_app="codex",
            host_session_key="missing-thread",
            search_roots=[tmp_path / "missing-root"],
        )
