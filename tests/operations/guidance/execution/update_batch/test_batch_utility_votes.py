"""Batch utility-vote contracts."""

from pathlib import Path

from app.startup.agent_operations import handle_events, handle_update


def test_update_batch_should_apply_multiple_utility_votes_and_clear_pending_candidates(
    codex_runtime_identity,
    codex_transcript_fixture,
    repo_with_shellbrain_state: Path,
    uow_factory,
    seed_memory,
    fetch_rows,
) -> None:
    """update batch should always apply multiple utility votes and clear pending candidates."""

    seed_memory(memory_id="problem-1", repo_id="repo-under-test", scope="repo", kind="problem", text_value="Problem")
    seed_memory(memory_id="fact-1", repo_id="repo-under-test", scope="repo", kind="fact", text_value="Fact 1")
    seed_memory(memory_id="fact-2", repo_id="repo-under-test", scope="repo", kind="fact", text_value="Fact 2")

    events_result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="repo-under-test",
        repo_root=repo_with_shellbrain_state,
        search_roots_by_host={"codex": list(codex_transcript_fixture["search_roots"]), "claude_code": []},
    )
    assert events_result["status"] == "ok"

    result = handle_update(
        {
            "updates": [
                {"memory_id": "fact-1", "update": {"type": "utility_vote", "problem_id": "problem-1", "vote": 1.0}},
                {"memory_id": "fact-2", "update": {"type": "utility_vote", "problem_id": "problem-1", "vote": -1.0}},
            ]
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-under-test",
        repo_root=repo_with_shellbrain_state,
    )

    assert result["status"] == "ok"
    rows = fetch_rows(__import__("app.infrastructure.db.models.utility", fromlist=["utility_observations"]).utility_observations)
    assert len(rows) == 2
    assert result["data"]["applied_count"] == 2
