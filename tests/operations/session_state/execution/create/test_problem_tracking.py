"""Create-driven problem tracking contracts."""

from pathlib import Path

from tests.operations._shared.handler_calls import handle_memory_add, handle_events
from app.infrastructure.local_state.session_state_file_store import (
    FileSessionStateStore,
)


def test_create_problem_should_set_current_problem_id_in_trusted_session_state(
    codex_runtime_identity,
    codex_transcript_fixture,
    repo_with_shellbrain_state: Path,
    uow_factory,
    stub_embedding_provider,
) -> None:
    """create problem should always set current_problem_id in trusted session state."""

    events_result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="repo-under-test",
        repo_root=repo_with_shellbrain_state,
        search_roots_by_host={
            "codex": list(codex_transcript_fixture["search_roots"]),
            "claude_code": [],
        },
    )
    evidence_ref = events_result["data"]["events"][0]["id"]

    result = handle_memory_add(
        {
            "memory": {
                "text": "Current problem.",
                "kind": "problem",
                "evidence_refs": [evidence_ref],
            }
        },
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: stub_embedding_provider,
        embedding_model="stub-v1",
        inferred_repo_id="repo-under-test",
        defaults={"scope": "repo"},
        repo_root=repo_with_shellbrain_state,
    )

    assert result["status"] == "ok"
    state = FileSessionStateStore().load(
        repo_root=repo_with_shellbrain_state,
        caller_id=codex_runtime_identity["canonical_id"],
    )
    assert state is not None
    assert state.current_problem_id == result["data"]["memory_id"]
