"""Claude Code transcript discovery guardrails."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.infrastructure.host_apps.transcripts.claude_code import (
    list_claude_code_sessions_for_repo,
)


def test_claude_code_session_listing_does_not_scan_arbitrary_home_subdirectories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Claude discovery should not fall back to a full home-directory crawl."""

    repo_root = Path.cwd().resolve()
    cli_session_id = "46cc92ee-1291-49d2-89e5-ef0ac1603709"
    unrelated_metadata_path = tmp_path / "Contacts" / "local_private.json"
    unrelated_metadata_path.parent.mkdir(parents=True)
    unrelated_metadata_path.write_text(
        json.dumps(
            {
                "sessionId": "local-private",
                "cliSessionId": cli_session_id,
                "cwd": str(repo_root),
            }
        ),
        encoding="utf-8",
    )
    transcript_path = (
        tmp_path
        / ".claude"
        / "projects"
        / str(repo_root).replace("/", "-")
        / f"{cli_session_id}.jsonl"
    )
    transcript_path.parent.mkdir(parents=True)
    transcript_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    candidates = list_claude_code_sessions_for_repo(
        repo_root=repo_root,
        search_roots=[tmp_path],
    )

    assert candidates == []
