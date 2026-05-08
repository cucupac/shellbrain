"""Fallback identity behavior contracts."""

from pathlib import Path

from app.periphery.host_identity.resolver import discover_untrusted_events_candidate


def test_identity_fallback_should_mark_the_discovered_events_candidate_untrusted_when_no_runtime_identity_exists(
    codex_transcript_fixture,
) -> None:
    """identity fallback should always mark the discovered events candidate untrusted when no runtime identity exists."""

    candidate = discover_untrusted_events_candidate(
        repo_root=Path.cwd().resolve(),
        search_roots_by_host={"codex": list(codex_transcript_fixture["search_roots"]), "claude_code": []},
    )

    assert candidate is not None
    assert candidate.caller_identity is not None
    assert candidate.caller_identity.trust_level == "untrusted"
    assert candidate.caller_identity.canonical_id == codex_transcript_fixture["canonical_thread_id"]
