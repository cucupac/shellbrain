"""Shared fixtures for episodic-ingestion tests."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from tests.operations._shared.integration_db_fixtures import (  # noqa: F401
    admin_db_dsn,
    clear_host_runtime_identity,
    clear_database,
    count_rows,
    db_dsn,
    fetch_rows,
    integration_admin_engine,
    integration_engine,
    integration_session_factory,
    seed_memory,
    stub_embedding_provider,
    uow_factory,
)


def _claude_project_slug(repo_root: Path) -> str:
    """Match Claude Code's cwd-to-project-folder encoding without hard-coded local paths."""

    return str(repo_root.resolve()).replace("/", "-")


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
            "text": "README.md\napp/\ninsights/\n",
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
        {
            "timestamp": "2026-03-12T01:44:31Z",
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "last_token_usage": {
                        "input_tokens": 1200,
                        "cached_input_tokens": 300,
                        "output_tokens": 90,
                        "reasoning_output_tokens": 25,
                    },
                    "model_context_window": 258400,
                },
            },
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
    repo_root = Path.cwd().resolve()
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
                "cwd": str(repo_root),
            }
        ),
        encoding="utf-8",
    )

    transcript_root = tmp_path / ".claude" / "projects" / _claude_project_slug(repo_root)
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
                "model": "claude-opus-4-6",
                "role": "assistant",
                "content": [{"type": "text", "text": "I will inspect the workflow."}],
                "usage": {
                    "input_tokens": 80,
                    "cache_creation_input_tokens": 20,
                    "cache_read_input_tokens": 10,
                    "output_tokens": 12,
                },
            },
        },
        {
            "uuid": "claude-tool-noise-1",
            "timestamp": "2026-03-12T02:01:20Z",
            "type": "user",
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "text": "ls\nREADME.md\napp/\n", "is_error": False}],
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


@pytest.fixture
def cursor_transcript_fixture(tmp_path: Path) -> dict[str, object]:
    """Provide one synthetic Cursor workspace/global state pair with active composer data."""

    composer_id = "cursor-composer-1"
    workspace_id = "cursor-workspace-1"
    repo_root = Path.cwd().resolve()
    cursor_user_root = tmp_path / "Cursor" / "User"
    workspace_root = cursor_user_root / "workspaceStorage" / workspace_id
    global_db = cursor_user_root / "globalStorage" / "state.vscdb"
    workspace_db = workspace_root / "state.vscdb"
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "workspace.json").write_text(
        json.dumps({"folder": repo_root.as_uri()}),
        encoding="utf-8",
    )

    _write_item_table_json(
        workspace_db,
        {
            "composer.composerData": {
                "allComposers": [{"composerId": composer_id}],
                "selectedComposerIds": [composer_id],
                "lastFocusedComposerIds": [composer_id],
                "hasMigratedComposerData": True,
                "hasMigratedMultipleComposers": True,
            }
        },
    )

    user_bubble_id = "cursor-bubble-user-1"
    assistant_bubble_id = "cursor-bubble-assistant-1"
    rich_text_bubble_id = "cursor-bubble-richtext-1"
    tool_bubble_id = "cursor-bubble-tool-1"
    generating_bubble_id = "cursor-bubble-generating-1"

    _write_cursor_disk_kv(
        global_db,
        {
            f"composerData:{composer_id}": {
                "composerId": composer_id,
                "createdAt": 1_774_450_800_000,
                "lastUpdatedAt": 1_774_450_840_000,
                "fullConversationHeadersOnly": [
                    {"bubbleId": user_bubble_id},
                    {"bubbleId": assistant_bubble_id},
                    {"bubbleId": rich_text_bubble_id},
                    {"bubbleId": tool_bubble_id},
                    {"bubbleId": generating_bubble_id},
                ],
                "generatingBubbleIds": [generating_bubble_id],
            },
            f"bubbleId:{composer_id}:{user_bubble_id}": {
                "bubbleId": user_bubble_id,
                "createdAt": 1_774_450_801_000,
                "type": 1,
                "text": "Fix the smoke workflow.",
            },
            f"bubbleId:{composer_id}:{assistant_bubble_id}": {
                "bubbleId": assistant_bubble_id,
                "createdAt": 1_774_450_802_000,
                "type": 2,
                "text": "I will inspect the workflow.",
                "requestId": "cursor-request-1",
                "model": "claude-3-7-sonnet",
                "tokenCount": {
                    "inputTokens": 44,
                    "outputTokens": 11,
                },
            },
            f"bubbleId:{composer_id}:{rich_text_bubble_id}": {
                "bubbleId": rich_text_bubble_id,
                "createdAt": 1_774_450_803_000,
                "type": 2,
                "text": "",
                "richText": json.dumps(
                    {
                        "root": {
                            "children": [
                                {
                                    "type": "paragraph",
                                    "children": [
                                        {
                                            "type": "text",
                                            "text": "Rich text fallback still becomes a message.",
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                ),
            },
            f"bubbleId:{composer_id}:{tool_bubble_id}": {
                "bubbleId": tool_bubble_id,
                "createdAt": 1_774_450_804_000,
                "type": 2,
                "requestId": "cursor-request-2",
                "model": "claude-3-7-sonnet",
                "text": "The test run failed.",
                "tokenCount": {
                    "inputTokens": 30,
                    "outputTokens": 8,
                },
                "toolResults": [
                    {
                        "toolName": "Bash",
                        "status": "error",
                        "summary": "pytest failed",
                        "text": "1 failed, 127 passed",
                        "command": "pytest tests/smoke.py",
                    }
                ],
                "assistantSuggestedDiffs": [
                    {
                        "relativePath": "app/workflows/smoke.yml",
                    }
                ],
            },
            f"bubbleId:{composer_id}:{generating_bubble_id}": {
                "bubbleId": generating_bubble_id,
                "createdAt": 1_774_450_805_000,
                "type": 2,
                "text": "This unfinished message should not be imported.",
            },
            f"messageRequestContext:{composer_id}:{tool_bubble_id}": {
                "todos": [{"text": "ignored context row"}],
                "cursorRules": [],
            },
        },
    )

    return {
        "host_app": "cursor",
        "host_session_key": composer_id,
        "canonical_thread_id": f"cursor:{composer_id}",
        "search_roots": [cursor_user_root],
        "transcript_path": global_db,
        "workspace_db": workspace_db,
        "entries": {
            "user_bubble_id": user_bubble_id,
            "assistant_bubble_id": assistant_bubble_id,
            "rich_text_bubble_id": rich_text_bubble_id,
            "tool_bubble_id": tool_bubble_id,
            "generating_bubble_id": generating_bubble_id,
        },
    }


def _write_jsonl(path: Path, entries: list[dict[str, object]]) -> None:
    """Write one JSONL file with deterministic newline termination."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(f"{json.dumps(entry)}\n" for entry in entries)
    path.write_text(payload, encoding="utf-8")


def _write_item_table_json(path: Path, payloads: dict[str, dict[str, object]]) -> None:
    """Write one tiny Cursor workspace ItemTable database."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        for key, value in payloads.items():
            conn.execute("INSERT INTO ItemTable (key, value) VALUES (?, ?)", (key, json.dumps(value)))


def _write_cursor_disk_kv(path: Path, payloads: dict[str, dict[str, object]]) -> None:
    """Write one tiny Cursor global cursorDiskKV database."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")
        for key, value in payloads.items():
            conn.execute("INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)", (key, json.dumps(value)))
