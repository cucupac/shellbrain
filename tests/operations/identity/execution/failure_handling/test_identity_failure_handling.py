"""Identity compatibility failure contracts."""

from pathlib import Path

from app.infrastructure.host_identity.resolver import resolve_caller_identity, resolve_trusted_events_source


def test_identity_failure_handling_should_return_host_hook_missing_when_claude_runtime_is_detected_without_trusted_shellbrain_identity(
    claude_runtime_without_hook,
) -> None:
    """identity failure handling should always return host_hook_missing when Claude runtime is detected without trusted Shellbrain identity."""

    resolved = resolve_caller_identity()

    assert resolved.caller_identity is None
    assert resolved.error is not None
    assert resolved.error.code.value == "host_hook_missing"


def test_identity_failure_handling_should_return_host_identity_drifted_when_one_trusted_identity_transcript_cannot_be_resolved(
    codex_runtime_identity,
    tmp_path: Path,
) -> None:
    """identity failure handling should always return host_identity_drifted when one trusted identity transcript cannot be resolved."""

    resolved = resolve_caller_identity()

    assert resolved.caller_identity is not None
    source = resolve_trusted_events_source(
        caller_identity=resolved.caller_identity,
        repo_root=tmp_path / "missing-repo",
        search_roots_by_host={"codex": [tmp_path / "missing-transcripts"], "claude_code": []},
    )

    assert source.caller_identity is not None
    assert source.error is not None
    assert source.error.code.value == "host_identity_drifted"
