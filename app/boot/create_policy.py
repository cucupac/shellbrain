"""Boot-time helpers for normalized create-policy settings."""

from typing import Any

from app.boot.config import get_config_provider
from app.core.contracts.errors import ErrorCode, ErrorDetail


_SUPPORTED_GATES = ("schema", "semantic", "integrity")


def get_create_policy_settings() -> dict[str, Any]:
    """Return normalized create-policy settings from YAML config."""

    policy = get_config_provider().get_create_policy()
    configured_gates = policy.get("gates") or list(_SUPPORTED_GATES)
    gates = [str(gate) for gate in configured_gates if str(gate) in _SUPPORTED_GATES]
    if "schema" not in gates:
        raise ValueError("create_policy.gates must include schema")
    return {"gates": gates}


def validate_create_policy_settings() -> list[ErrorDetail]:
    """Return structured config errors for unsupported create-policy settings."""

    try:
        get_create_policy_settings()
    except ValueError as exc:
        return [ErrorDetail(code=ErrorCode.INTERNAL_ERROR, message=str(exc), field="create_policy.gates")]
    return []
