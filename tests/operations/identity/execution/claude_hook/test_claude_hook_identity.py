"""Claude hook identity contracts."""

from shellbrain.periphery.identity.resolver import resolve_caller_identity


def test_claude_hook_identity_should_resolve_one_trusted_main_caller_from_shellbrain_hook_env(
    claude_hook_runtime_identity,
) -> None:
    """claude hook identity should always resolve one trusted main caller from Shellbrain hook env."""

    resolved = resolve_caller_identity()

    assert resolved.error is None
    assert resolved.caller_identity is not None
    assert resolved.caller_identity.host_app == "claude_code"
    assert resolved.caller_identity.canonical_id == claude_hook_runtime_identity["canonical_id"]
    assert resolved.caller_identity.trust_level == "trusted"


def test_claude_hook_identity_should_resolve_one_trusted_subagent_caller_when_agent_key_is_present(
    claude_hook_subagent_runtime_identity,
) -> None:
    """claude hook identity should always resolve one trusted subagent caller when agent_key is present."""

    resolved = resolve_caller_identity()

    assert resolved.error is None
    assert resolved.caller_identity is not None
    assert resolved.caller_identity.agent_key == claude_hook_subagent_runtime_identity["agent_key"]
    assert resolved.caller_identity.canonical_id == claude_hook_subagent_runtime_identity["canonical_id"]
    assert resolved.caller_identity.trust_level == "trusted"
