"""Failure-handling contracts for episodic transcript imports."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from app.core.use_cases.sync_episode import sync_episode_from_host
from app.periphery.db.uow import PostgresUnitOfWork


def test_episode_import_surfaces_a_user_actionable_error_when_a_host_source_disappears(
    uow_factory: Callable[[], PostgresUnitOfWork],
    tmp_path: Path,
) -> None:
    """episode import should always surface a user-actionable error when a host source disappears."""

    with uow_factory() as uow:
        with pytest.raises(FileNotFoundError, match="codex|Codex"):
            sync_episode_from_host(
                repo_id="repo-a",
                host_app="codex",
                host_session_key="missing-thread",
                uow=uow,
                search_roots=[tmp_path / "missing-root"],
            )


def test_episode_import_rolls_back_partial_writes_if_a_db_write_fails_mid_import(
    codex_transcript_fixture: dict[str, object],
    uow_factory: Callable[[], PostgresUnitOfWork],
    count_rows: Callable[[str], int],
) -> None:
    """episode import should always roll back partial writes if a DB write fails mid-import."""

    with pytest.raises(RuntimeError, match="boom"):
        with uow_factory() as uow:
            original_append_event = uow.episodes.append_event
            call_count = 0

            def _boom(event) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise RuntimeError("boom")
                original_append_event(event)

            uow.episodes.append_event = _boom
            sync_episode_from_host(
                repo_id="repo-a",
                host_app="codex",
                host_session_key=str(codex_transcript_fixture["host_session_key"]),
                uow=uow,
                search_roots=list(codex_transcript_fixture["search_roots"]),
            )

    assert count_rows("episodes") == 0
    assert count_rows("episode_events") == 0
