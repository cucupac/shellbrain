"""Session idle-expiry contracts."""

from app.core.entities.session_state import SessionState
from app.handlers.session_state import SessionStateManager


def test_idle_expiry_should_reset_working_session_fields_after_24_hours(
    old_timestamp: str,
) -> None:
    """idle expiry should always reset working-session fields after 24 hours."""

    state = SessionState(
        caller_id="codex:thread-a",
        host_app="codex",
        host_session_key="thread-a",
        agent_key=None,
        session_started_at=old_timestamp,
        last_seen_at=old_timestamp,
        current_problem_id="problem-1",
        last_events_episode_id="episode-1",
        last_events_event_ids=["evt-1"],
        last_events_at=old_timestamp,
        last_guidance_at=old_timestamp,
        last_guidance_problem_id="problem-1",
    )

    refreshed = SessionStateManager.reset_if_idle(
        state, now_iso="2026-03-18T12:00:00+00:00"
    )

    assert refreshed.current_problem_id is None
    assert refreshed.last_events_episode_id is None
    assert refreshed.last_events_event_ids == []
    assert refreshed.last_guidance_problem_id is None
