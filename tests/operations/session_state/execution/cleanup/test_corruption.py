"""Session-state corruption contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.infrastructure.local_state.session_state_file_store import (
    FileSessionStateStore,
    SessionStateFileCorruptionError,
)


def test_session_state_load_should_raise_for_malformed_json(
    repo_with_shellbrain_state: Path,
) -> None:
    """malformed session-state JSON should not look like missing state."""

    state_path = _state_path(repo_with_shellbrain_state, caller_id="codex:thread-a")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(SessionStateFileCorruptionError, match="invalid JSON"):
        FileSessionStateStore().load(
            repo_root=repo_with_shellbrain_state, caller_id="codex:thread-a"
        )

    assert state_path.exists()


def test_session_state_load_should_raise_for_non_object_payload(
    repo_with_shellbrain_state: Path,
) -> None:
    """non-object session-state JSON should not look like missing state."""

    state_path = _state_path(repo_with_shellbrain_state, caller_id="codex:thread-a")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("[]", encoding="utf-8")

    with pytest.raises(SessionStateFileCorruptionError, match="JSON object"):
        FileSessionStateStore().load(
            repo_root=repo_with_shellbrain_state, caller_id="codex:thread-a"
        )

    assert state_path.exists()


def test_session_state_list_should_raise_for_corrupt_state_file(
    repo_with_shellbrain_state: Path,
    write_session_state,
) -> None:
    """session-state list should not silently skip corrupt persisted state."""

    write_session_state(
        host_app="codex",
        caller_id="codex:thread-a",
        payload=_valid_payload(caller_id="codex:thread-a"),
    )
    state_path = _state_path(repo_with_shellbrain_state, caller_id="codex:thread-b")
    state_path.write_text("[]", encoding="utf-8")

    with pytest.raises(SessionStateFileCorruptionError, match="JSON object"):
        FileSessionStateStore().list(repo_root=repo_with_shellbrain_state)


def test_session_state_gc_should_not_delete_when_any_state_file_is_corrupt(
    repo_with_shellbrain_state: Path,
    write_session_state,
    old_timestamp: str,
) -> None:
    """session-state gc should not turn corrupt timestamps into stale deletions."""

    stale_path = write_session_state(
        host_app="codex",
        caller_id="codex:thread-a",
        payload=_valid_payload(caller_id="codex:thread-a", last_seen_at=old_timestamp),
    )
    corrupt_path = write_session_state(
        host_app="codex",
        caller_id="codex:thread-b",
        payload=_valid_payload(
            caller_id="codex:thread-b", last_seen_at="not-a-timestamp"
        ),
    )

    with pytest.raises(SessionStateFileCorruptionError, match="last_seen_at"):
        FileSessionStateStore().gc(
            repo_root=repo_with_shellbrain_state,
            older_than_iso="2026-03-18T12:00:00+00:00",
        )

    assert stale_path.exists()
    assert corrupt_path.exists()


def _state_path(repo_root: Path, *, caller_id: str) -> Path:
    return (
        repo_root
        / ".shellbrain"
        / "session_state"
        / "codex"
        / f"{caller_id.replace(':', '__')}.json"
    )


def _valid_payload(
    *, caller_id: str, last_seen_at: str | None = None
) -> dict[str, object]:
    return {
        "caller_id": caller_id,
        "host_app": "codex",
        "host_session_key": caller_id.split(":", 1)[1],
        "agent_key": None,
        "session_started_at": "2026-03-18T10:00:00+00:00",
        "last_seen_at": last_seen_at or "2026-03-18T10:00:00+00:00",
    }
