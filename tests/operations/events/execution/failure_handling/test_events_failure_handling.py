"""Failure-handling contracts for active-episode event browsing."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.periphery.cli.handlers import handle_events
from app.periphery.db.uow import PostgresUnitOfWork


def test_events_errors_clearly_when_no_active_session_exists(
    tmp_path: Path,
    uow_factory: Callable[[], PostgresUnitOfWork],
) -> None:
    """events should always return not_found when no active host session exists for the repo."""

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
    assert any(error["code"] == "not_found" for error in result["errors"])
