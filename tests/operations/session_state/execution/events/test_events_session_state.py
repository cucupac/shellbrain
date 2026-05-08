"""Events-driven session-state contracts."""

from pathlib import Path

from app.startup.agent_operations import handle_events
from app.infrastructure.local_state.session_state_file_store import FileSessionStateStore


def test_events_should_persist_trusted_caller_session_state(
    codex_runtime_identity,
    codex_transcript_fixture,
    repo_with_shellbrain_state: Path,
    uow_factory,
) -> None:
    """events should always persist trusted caller session state."""

    result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="repo-under-test",
        repo_root=repo_with_shellbrain_state,
        search_roots_by_host={"codex": list(codex_transcript_fixture["search_roots"]), "claude_code": []},
    )

    assert result["status"] == "ok"
    state = FileSessionStateStore().load(repo_root=repo_with_shellbrain_state, caller_id=codex_runtime_identity["canonical_id"])
    assert state is not None
    assert state.caller_id == codex_runtime_identity["canonical_id"]
    assert state.last_events_episode_id == result["data"]["episode_id"]
    assert state.last_events_event_ids
