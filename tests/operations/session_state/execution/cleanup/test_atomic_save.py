"""Session-state save hardening contracts."""

from __future__ import annotations

from app.core.entities.session_state import SessionState
from app.periphery.session_state.file_store import FileSessionStateStore


def test_session_state_save_should_update_in_place_without_temp_file_leaks(repo_with_shellbrain_state) -> None:
    """session state save should atomically replace the caller file without leaking temp files."""

    store = FileSessionStateStore()
    initial = SessionState(
        caller_id="codex:thread-a",
        host_app="codex",
        host_session_key="thread-a",
        agent_key=None,
        session_started_at="2026-03-19T00:00:00+00:00",
        last_seen_at="2026-03-19T00:05:00+00:00",
        current_problem_id=None,
        last_events_episode_id=None,
        last_events_event_ids=[],
        last_events_at=None,
        last_guidance_at=None,
        last_guidance_problem_id=None,
    )
    updated = SessionState(
        **{
            **initial.__dict__,
            "last_seen_at": "2026-03-19T00:10:00+00:00",
            "current_problem_id": "mem-problem-1",
        }
    )

    store.save(repo_root=repo_with_shellbrain_state, state=initial)
    store.save(repo_root=repo_with_shellbrain_state, state=updated)

    state_dir = repo_with_shellbrain_state / ".shellbrain" / "session_state" / "codex"
    saved_files = sorted(state_dir.glob("*"))
    loaded = store.load(repo_root=repo_with_shellbrain_state, caller_id="codex:thread-a")

    assert [path.name for path in saved_files] == ["codex__thread-a.json"]
    assert loaded is not None
    assert loaded.current_problem_id == "mem-problem-1"
    assert loaded.last_seen_at == "2026-03-19T00:10:00+00:00"


def test_session_state_delete_should_only_remove_the_named_caller(repo_with_shellbrain_state) -> None:
    """session state clear should only delete the explicitly named caller file."""

    store = FileSessionStateStore()
    state_a = SessionState(
        caller_id="codex:thread-a",
        host_app="codex",
        host_session_key="thread-a",
        agent_key=None,
        session_started_at="2026-03-19T00:00:00+00:00",
        last_seen_at="2026-03-19T00:05:00+00:00",
        current_problem_id=None,
        last_events_episode_id=None,
        last_events_event_ids=[],
        last_events_at=None,
        last_guidance_at=None,
        last_guidance_problem_id=None,
    )
    state_b = SessionState(
        **{
            **state_a.__dict__,
            "caller_id": "codex:thread-b",
            "host_session_key": "thread-b",
        }
    )

    store.save(repo_root=repo_with_shellbrain_state, state=state_a)
    store.save(repo_root=repo_with_shellbrain_state, state=state_b)
    store.delete(repo_root=repo_with_shellbrain_state, caller_id="codex:thread-a")

    assert store.load(repo_root=repo_with_shellbrain_state, caller_id="codex:thread-a") is None
    assert store.load(repo_root=repo_with_shellbrain_state, caller_id="codex:thread-b") is not None
