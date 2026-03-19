"""Shared runtime-identity fixtures for host integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def codex_runtime_identity(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Provide one trusted Codex runtime identity via environment variables."""

    thread_id = "019ce136-e14d-7b80-92bc-be07e4330536"
    monkeypatch.setenv("CODEX_THREAD_ID", thread_id)
    monkeypatch.delenv("SHELLBRAIN_HOST_APP", raising=False)
    monkeypatch.delenv("SHELLBRAIN_HOST_SESSION_KEY", raising=False)
    monkeypatch.delenv("SHELLBRAIN_AGENT_KEY", raising=False)
    monkeypatch.delenv("SHELLBRAIN_TRANSCRIPT_PATH", raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    return {
        "host_app": "codex",
        "host_session_key": thread_id,
        "canonical_id": f"codex:{thread_id}",
    }


@pytest.fixture
def claude_hook_runtime_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Provide one trusted Claude runtime identity via Shellbrain hook variables."""

    session_id = "46cc92ee-1291-49d2-89e5-ef0ac1603709"
    transcript_path = tmp_path / ".claude" / "projects" / "-Users-adamcuculich-memory" / f"{session_id}.jsonl"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        json.dumps(
            {
                "uuid": "claude-user-1",
                "timestamp": "2026-03-18T12:00:00Z",
                "type": "user",
                "message": {"role": "user", "content": [{"type": "text", "text": "Inspect this bug."}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("SHELLBRAIN_HOST_APP", "claude_code")
    monkeypatch.setenv("SHELLBRAIN_HOST_SESSION_KEY", session_id)
    monkeypatch.setenv("SHELLBRAIN_TRANSCRIPT_PATH", str(transcript_path))
    monkeypatch.setenv("SHELLBRAIN_CALLER_ID", f"claude_code:{session_id}")
    monkeypatch.delenv("SHELLBRAIN_AGENT_KEY", raising=False)
    return {
        "host_app": "claude_code",
        "host_session_key": session_id,
        "transcript_path": str(transcript_path),
        "canonical_id": f"claude_code:{session_id}",
    }


@pytest.fixture
def claude_hook_subagent_runtime_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Provide one trusted Claude subagent identity via Shellbrain hook variables."""

    session_id = "46cc92ee-1291-49d2-89e5-ef0ac1603709"
    agent_id = "agent-explore-1"
    transcript_path = (
        tmp_path
        / ".claude"
        / "projects"
        / "-Users-adamcuculich-memory"
        / session_id
        / "subagents"
        / f"{agent_id}.jsonl"
    )
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        json.dumps(
            {
                "uuid": "claude-agent-user-1",
                "timestamp": "2026-03-18T12:00:00Z",
                "type": "user",
                "message": {"role": "user", "content": [{"type": "text", "text": "Subagent task."}]},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("SHELLBRAIN_HOST_APP", "claude_code")
    monkeypatch.setenv("SHELLBRAIN_HOST_SESSION_KEY", session_id)
    monkeypatch.setenv("SHELLBRAIN_AGENT_KEY", agent_id)
    monkeypatch.setenv("SHELLBRAIN_TRANSCRIPT_PATH", str(transcript_path))
    monkeypatch.setenv("SHELLBRAIN_CALLER_ID", f"claude_code:{session_id}:agent:{agent_id}")
    return {
        "host_app": "claude_code",
        "host_session_key": session_id,
        "agent_key": agent_id,
        "transcript_path": str(transcript_path),
        "canonical_id": f"claude_code:{session_id}:agent:{agent_id}",
    }


@pytest.fixture
def claude_runtime_without_hook(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Provide one Claude runtime hint without trusted Shellbrain hook identity."""

    session_id = "46cc92ee-1291-49d2-89e5-ef0ac1603709"
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("SHELLBRAIN_HOST_APP", raising=False)
    monkeypatch.delenv("SHELLBRAIN_HOST_SESSION_KEY", raising=False)
    monkeypatch.delenv("SHELLBRAIN_AGENT_KEY", raising=False)
    monkeypatch.delenv("SHELLBRAIN_TRANSCRIPT_PATH", raising=False)
    monkeypatch.delenv("SHELLBRAIN_CALLER_ID", raising=False)
    monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
    return {"session_id": session_id}
