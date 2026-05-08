"""Session-state cleanup contracts."""

from pathlib import Path

from app.periphery.local_state.session_state_file_store import FileSessionStateStore


def test_session_state_gc_should_remove_stale_state_files_after_7_days(
    repo_with_shellbrain_state: Path,
    write_session_state,
    old_timestamp: str,
) -> None:
    """session state gc should always remove stale state files after 7 days."""

    state_path = write_session_state(
        host_app="codex",
        caller_id="codex:thread-a",
        payload={
            "caller_id": "codex:thread-a",
            "host_app": "codex",
            "host_session_key": "thread-a",
            "agent_key": None,
            "session_started_at": old_timestamp,
            "last_seen_at": old_timestamp,
        },
    )

    deleted = FileSessionStateStore().gc(repo_root=repo_with_shellbrain_state, older_than_iso="2026-03-18T12:00:00+00:00")

    assert deleted == ["codex:thread-a"]
    assert not state_path.exists()
