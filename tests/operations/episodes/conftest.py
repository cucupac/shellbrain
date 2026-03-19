"""Shared fixtures for episodic-ingestion tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.operations._shared.integration_db_fixtures import (
    clear_host_runtime_identity,
    clear_database,
    count_rows,
    db_dsn,
    fetch_rows,
    integration_engine,
    integration_session_factory,
    seed_memory,
    stub_embedding_provider,
    uow_factory,
)


@pytest.fixture
def codex_transcript_fixture(tmp_path: Path) -> dict[str, object]:
    """Provide one synthetic Codex transcript with meaningful and noisy tool events."""

    thread_id = "019ce136-e14d-7b80-92bc-be07e4330536"
    transcript_root = tmp_path / "codex-root" / ".codex" / "sessions"
    transcript_path = transcript_root / "2026" / "03" / "12" / f"rollout-2026-03-12T01-43-16-{thread_id}.jsonl"
    session_meta = {
        "type": "session_meta",
        "payload": {
            "id": thread_id,
            "cwd": str(Path.cwd().resolve()),
        },
    }
    entries = [
        {
            "event_id": "codex-user-1",
            "timestamp": "2026-03-12T01:44:00Z",
            "type": "message",
            "role": "user",
            "text": "Fix the smoke workflow.",
        },
        {
            "event_id": "codex-assistant-1",
            "timestamp": "2026-03-12T01:44:15Z",
            "type": "message",
            "role": "assistant",
            "text": "I will inspect the workflow.",
        },
        {
            "event_id": "codex-tool-noise-1",
            "timestamp": "2026-03-12T01:44:20Z",
            "type": "tool_result",
            "tool_name": "exec_command",
            "status": "ok",
            "summary": "ls",
            "text": "README.md\nshellbrain/\ninsights/\n",
        },
        {
            "event_id": "codex-tool-important-1",
            "timestamp": "2026-03-12T01:44:30Z",
            "type": "tool_result",
            "tool_name": "exec_command",
            "status": "error",
            "summary": "pytest failed",
            "text": "1 failed, 127 passed",
        },
    ]
    _write_jsonl(transcript_path, [session_meta, *entries])
    return {
        "host_app": "codex",
        "host_session_key": thread_id,
        "canonical_thread_id": f"codex:{thread_id}",
        "search_roots": [transcript_root],
        "transcript_path": transcript_path,
        "entries": entries,
    }


@pytest.fixture
def claude_code_transcript_fixture(tmp_path: Path) -> dict[str, object]:
    """Provide one synthetic Claude Code transcript plus its local metadata file."""

    local_session_id = "local_9d640378-6572-4541-8db1-f2f3c241484e"
    cli_session_id = "46cc92ee-1291-49d2-89e5-ef0ac1603709"
    metadata_root = (
        tmp_path
        / "Library"
        / "Application Support"
        / "Claude"
        / "claude-code-sessions"
        / "account-a"
        / "org-a"
    )
    metadata_path = metadata_root / f"{local_session_id}.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(
            {
                "sessionId": local_session_id,
                "cliSessionId": cli_session_id,
                "cwd": "/Users/example/memory",
            }
        ),
        encoding="utf-8",
    )

    transcript_root = tmp_path / ".claude" / "projects" / "-Users-example-memory"
    transcript_path = transcript_root / f"{cli_session_id}.jsonl"
    entries = [
        {
            "uuid": "claude-user-1",
            "timestamp": "2026-03-12T02:01:00Z",
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "Fix the smoke workflow."}],
            },
        },
        {
            "uuid": "claude-assistant-1",
            "timestamp": "2026-03-12T02:01:15Z",
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "I will inspect the workflow."}],
            },
        },
        {
            "uuid": "claude-tool-noise-1",
            "timestamp": "2026-03-12T02:01:20Z",
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "text": "ls\nREADME.md\nshellbrain/\n", "is_error": False}],
            },
        },
        {
            "uuid": "claude-tool-important-1",
            "timestamp": "2026-03-12T02:01:30Z",
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "text": "pytest failed: 1 failed, 127 passed", "is_error": True}],
            },
        },
    ]
    _write_jsonl(transcript_path, entries)
    return {
        "host_app": "claude_code",
        "host_session_key": cli_session_id,
        "canonical_thread_id": f"claude_code:{cli_session_id}",
        "local_session_id": local_session_id,
        "search_roots": [tmp_path],
        "transcript_path": transcript_path,
        "metadata_path": metadata_path,
        "entries": entries,
    }


def _write_jsonl(path: Path, entries: list[dict[str, object]]) -> None:
    """Write one JSONL file with deterministic newline termination."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(f"{json.dumps(entry)}\n" for entry in entries)
    path.write_text(payload, encoding="utf-8")
