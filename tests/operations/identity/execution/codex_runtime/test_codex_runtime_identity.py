"""Codex runtime identity contracts."""

from app.periphery.identity.resolver import resolve_caller_identity


def test_codex_runtime_identity_should_resolve_one_trusted_caller_from_codex_thread_id(codex_runtime_identity) -> None:
    """codex runtime identity should always resolve one trusted caller from CODEX_THREAD_ID."""

    resolved = resolve_caller_identity()

    assert resolved.error is None
    assert resolved.caller_identity is not None
    assert resolved.caller_identity.host_app == "codex"
    assert resolved.caller_identity.host_session_key == codex_runtime_identity["host_session_key"]
    assert resolved.caller_identity.canonical_id == codex_runtime_identity["canonical_id"]
    assert resolved.caller_identity.trust_level == "trusted"
