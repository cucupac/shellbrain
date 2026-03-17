"""Boot-time helpers for normalized create-policy settings."""

from typing import Any

from shellbrain.boot.config import get_config_provider
from shellbrain.core.contracts.errors import ErrorCode, ErrorDetail


_SUPPORTED_GATES = ("schema", "semantic", "integrity")
_SUPPORTED_SCOPES = ("repo", "global")


def get_create_policy_settings() -> dict[str, Any]:
    """Return normalized create-policy settings from YAML config."""

    policy = get_config_provider().get_create_policy()
    configured_gates = policy.get("gates")
    if not isinstance(configured_gates, list) or not configured_gates:
        raise ValueError("create_policy.gates must be a non-empty list")
    gates = [str(gate) for gate in configured_gates if str(gate) in _SUPPORTED_GATES]
    if len(gates) != len(configured_gates):
        raise ValueError("create_policy.gates contains unsupported values")
    if "schema" not in gates:
        raise ValueError("create_policy.gates must include schema")
    configured_defaults = policy.get("defaults")
    if not isinstance(configured_defaults, dict):
        raise ValueError("create_policy.defaults must be a mapping")
    scope = configured_defaults.get("scope")
    if not isinstance(scope, str) or scope not in _SUPPORTED_SCOPES:
        raise ValueError("create_policy.defaults.scope must be repo or global")
    return {
        "gates": gates,
        "defaults": {
            "scope": scope,
        },
    }


def get_create_hydration_defaults() -> dict[str, Any]:
    """Return normalized create defaults used by CLI hydration."""

    return dict(get_create_policy_settings()["defaults"])


def validate_create_policy_settings() -> list[ErrorDetail]:
    """Return structured config errors for unsupported create-policy settings."""

    try:
        get_create_policy_settings()
    except ValueError as exc:
        return [ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc), field="create_policy.gates")]
    return []
