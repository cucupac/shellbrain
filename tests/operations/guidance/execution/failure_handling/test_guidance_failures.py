"""Guidance-related failure contracts."""

from pathlib import Path

from app.startup.agent_operations import handle_update


def test_guidance_failures_should_require_events_when_batch_utility_votes_omit_evidence_and_no_recent_events_exist(
    repo_with_shellbrain_state: Path,
    uow_factory,
    seed_memory,
) -> None:
    """guidance failures should always require events when batch utility votes omit evidence and no recent events exist."""

    seed_memory(memory_id="problem-1", repo_id="repo-under-test", scope="repo", kind="problem", text_value="Problem")
    seed_memory(memory_id="fact-1", repo_id="repo-under-test", scope="repo", kind="fact", text_value="Fact")

    result = handle_update(
        {
            "updates": [
                {"memory_id": "fact-1", "update": {"type": "utility_vote", "problem_id": "problem-1", "vote": 1.0}},
            ]
        },
        uow_factory=uow_factory,
        inferred_repo_id="repo-under-test",
        repo_root=repo_with_shellbrain_state,
    )

    assert result["status"] == "error"
    assert result["errors"][0]["code"] == "semantic_error"
    assert "events" in result["errors"][0]["message"]
