"""Boot-time helpers for normalized update-policy settings."""

from typing import Any

from app.startup.config import get_config_provider
from app.core.contracts.errors import ErrorCode, ErrorDetail
from app.core.entities.settings import UpdatePolicySettings


_SUPPORTED_GATES = ("schema", "semantic", "integrity")


def get_typed_update_policy_settings() -> UpdatePolicySettings:
    """Return typed update-policy settings from YAML config."""

    policy = get_config_provider().get_update_policy()
    configured_gates = policy.get("gates")
    if not isinstance(configured_gates, list) or not configured_gates:
        raise ValueError("update_policy.gates must be a non-empty list")
    gates = [str(gate) for gate in configured_gates if str(gate) in _SUPPORTED_GATES]
    if len(gates) != len(configured_gates):
        raise ValueError("update_policy.gates contains unsupported values")
    if "schema" not in gates:
        raise ValueError("update_policy.gates must include schema")
    return UpdatePolicySettings(gates=tuple(gates))


def get_update_policy_settings() -> dict[str, Any]:
    """Return normalized update-policy settings from YAML config."""

    return get_typed_update_policy_settings().to_dict()


def validate_update_policy_settings() -> list[ErrorDetail]:
    """Return structured config errors for unsupported update-policy settings."""

    try:
        get_typed_update_policy_settings()
    except ValueError as exc:
        return [
            ErrorDetail(
                code=ErrorCode.INTERNAL_ERROR,
                message=str(exc),
                field="update_policy.gates",
            )
        ]
    return []
