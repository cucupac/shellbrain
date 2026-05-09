"""Per-caller session-state isolation contracts."""

from pathlib import Path

from app.core.entities.session_state import SessionState
from app.infrastructure.local_state.session_state_file_store import (
    FileSessionStateStore,
)


def test_multi_agent_isolation_should_keep_distinct_session_state_files_per_caller_id(
    repo_with_shellbrain_state: Path,
) -> None:
    """multi agent isolation should always keep distinct session state files per caller_id."""

    store = FileSessionStateStore()
    store.save(
        repo_root=repo_with_shellbrain_state,
        state=SessionState(
            caller_id="codex:thread-a",
            host_app="codex",
            host_session_key="thread-a",
            agent_key=None,
            session_started_at="2026-03-18T10:00:00+00:00",
            last_seen_at="2026-03-18T10:00:00+00:00",
        ),
    )
    store.save(
        repo_root=repo_with_shellbrain_state,
        state=SessionState(
            caller_id="claude_code:session-a:agent:agent-1",
            host_app="claude_code",
            host_session_key="session-a",
            agent_key="agent-1",
            session_started_at="2026-03-18T10:00:00+00:00",
            last_seen_at="2026-03-18T10:00:00+00:00",
        ),
    )

    assert (
        store.load(repo_root=repo_with_shellbrain_state, caller_id="codex:thread-a")
        is not None
    )
    assert (
        store.load(
            repo_root=repo_with_shellbrain_state,
            caller_id="claude_code:session-a:agent:agent-1",
        )
        is not None
    )
