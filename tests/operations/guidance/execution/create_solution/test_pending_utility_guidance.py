"""Solution-create guidance contracts."""

from pathlib import Path

from app.periphery.cli.handlers import handle_create, handle_events, handle_read


def test_create_solution_should_emit_pending_utility_votes_guidance_when_session_has_unrated_retrieved_memories(
    codex_runtime_identity,
    codex_transcript_fixture,
    repo_with_shellbrain_state: Path,
    uow_factory,
    stub_embedding_provider,
    seed_memory,
) -> None:
    """create solution should always emit pending_utility_votes guidance when session has unrated retrieved memories."""

    seed_memory(memory_id="problem-1", repo_id="repo-under-test", scope="repo", kind="problem", text_value="Problem")
    seed_memory(memory_id="fact-1", repo_id="repo-under-test", scope="repo", kind="fact", text_value="Helpful fact")

    events_result = handle_events(
        {},
        uow_factory=uow_factory,
        inferred_repo_id="repo-under-test",
        repo_root=repo_with_shellbrain_state,
        search_roots_by_host={"codex": list(codex_transcript_fixture["search_roots"]), "claude_code": []},
    )
    evidence_ref = events_result["data"]["events"][0]["id"]
    handle_create(
        {"memory": {"text": "Problem text.", "kind": "problem", "evidence_refs": [evidence_ref]}},
        uow_factory=uow_factory,
        embedding_provider_factory=lambda: stub_embedding_provider,
        embedding_model="stub-v1",
        inferred_repo_id="repo-under-test",
        defaults={"scope": "repo"},
        repo_root=repo_with_shellbrain_state,
    )
    read_result = handle_read(
        {"query": "Helpful fact", "mode": "targeted", "kinds": ["fact"]},
        uow_factory=uow_factory,
        inferred_repo_id="repo-under-test",
        repo_root=repo_with_shellbrain_state,
    )
    assert read_result["status"] == "ok"

    result = handle_create(
        {
            "memory": {
                    "text": "Solution text.",
                    "kind": "solution",
                    "links": {"problem_id": "problem-1"},
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
    guidance = result["data"].get("guidance", [])
    assert any(item["code"] == "pending_utility_votes" for item in guidance)
