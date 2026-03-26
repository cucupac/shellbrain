"""Shared session-state fixtures for working-memory tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def repo_with_shellbrain_state(tmp_path: Path) -> Path:
    """Provide one repo root with a writable .shellbrain runtime directory."""

    repo_root = tmp_path / "repo-under-test"
    (repo_root / ".shellbrain").mkdir(parents=True)
    return repo_root


@pytest.fixture
def write_session_state(repo_with_shellbrain_state: Path):
    """Provide helper for writing one raw session-state file."""

    def _write(*, host_app: str, caller_id: str, payload: dict[str, object]) -> Path:
        state_dir = repo_with_shellbrain_state / ".shellbrain" / "session_state" / host_app
        state_dir.mkdir(parents=True, exist_ok=True)
        path = state_dir / f"{caller_id.replace(':', '__')}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def old_timestamp() -> str:
    """Return one timestamp old enough to trigger idle/session-state GC behavior."""

    return "2026-03-10T00:00:00+00:00"
