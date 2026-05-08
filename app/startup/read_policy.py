"""Boot-time helpers for resolving YAML-backed read-policy settings."""

from typing import Any

from app.startup.config import get_config_provider
from app.core.entities.settings import ReadPolicySettings, SUPPORTED_READ_MODES


_SUPPORTED_MODES = SUPPORTED_READ_MODES
_SUPPORTED_BUCKETS = ("direct", "explicit", "implicit")
_EXPAND_INT_FIELDS = ("semantic_hops", "max_association_depth")
_EXPAND_BOOL_FIELDS = (
    "include_problem_links",
    "include_fact_update_links",
    "include_association_links",
)
_EXPAND_FLOAT_FIELDS = ("min_association_strength",)


def _require_mapping(value: Any, *, field: str) -> dict[str, Any]:
    """Require one config node to be a mapping."""

    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a mapping")
    return value


def _require_bool(mapping: dict[str, Any], key: str, *, field: str) -> bool:
    """Require one config value to be a boolean."""

    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{field}.{key} must be a boolean")
    return value


def _require_int(mapping: dict[str, Any], key: str, *, field: str) -> int:
    """Require one config value to be an integer."""

    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field}.{key} must be an integer")
    return int(value)


def _require_float(mapping: dict[str, Any], key: str, *, field: str) -> float:
    """Require one config value to be numeric."""

    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field}.{key} must be numeric")
    return float(value)


def _require_mode(value: Any, *, field: str) -> str:
    """Require one config value to be a supported read mode."""

    if not isinstance(value, str) or value not in _SUPPORTED_MODES:
        raise ValueError(f"{field} must be one of: {', '.join(_SUPPORTED_MODES)}")
    return value


def get_read_policy_settings() -> ReadPolicySettings:
    """Return typed read settings from YAML-backed runtime and policy config."""

    config_provider = get_config_provider()
    read_policy = _require_mapping(config_provider.get_read_policy(), field="read_policy")
    runtime = _require_mapping(config_provider.get_runtime(), field="runtime")
    cli_defaults = _require_mapping(runtime.get("cli"), field="runtime.cli")
    limits = _require_mapping(read_policy.get("limits"), field="read_policy.limits")
    expansion = _require_mapping(read_policy.get("expansion"), field="read_policy.expansion")
    quotas = _require_mapping(read_policy.get("quotas"), field="read_policy.quotas")
    weights = _require_mapping(read_policy.get("weights"), field="read_policy.weights")
    fusion = _require_mapping(read_policy.get("fusion"), field="read_policy.fusion")

    return ReadPolicySettings(
        default_mode=_require_mode(cli_defaults.get("default_mode"), field="runtime.cli.default_mode"),
        include_global=_require_bool(cli_defaults, "include_global", field="runtime.cli"),
        limits_by_mode={
            mode: _require_int(limits, mode, field="read_policy.limits")
            for mode in _SUPPORTED_MODES
        },
        expand={
            **{
                key: _require_int(expansion, key, field="read_policy.expansion")
                for key in _EXPAND_INT_FIELDS
            },
            **{
                key: _require_bool(expansion, key, field="read_policy.expansion")
                for key in _EXPAND_BOOL_FIELDS
            },
            **{
                key: _require_float(expansion, key, field="read_policy.expansion")
                for key in _EXPAND_FLOAT_FIELDS
            },
        },
        quotas_by_mode={
            mode: {
                bucket: _require_int(
                    _require_mapping(quotas.get(mode), field=f"read_policy.quotas.{mode}"),
                    bucket,
                    field=f"read_policy.quotas.{mode}",
                )
                for bucket in _SUPPORTED_BUCKETS
            }
            for mode in _SUPPORTED_MODES
        },
        retrieval={
            "semantic_weight": _require_float(weights, "semantic", field="read_policy.weights"),
            "keyword_weight": _require_float(weights, "keyword", field="read_policy.weights"),
            "k_rrf": _require_float(fusion, "k_rrf", field="read_policy.fusion"),
        },
    )


def get_read_settings() -> dict[str, Any]:
    """Return normalized read settings from YAML-backed runtime and policy config."""

    return get_read_policy_settings().to_dict()


def _coerce_read_policy_settings(settings: ReadPolicySettings | dict[str, Any]) -> ReadPolicySettings:
    if isinstance(settings, ReadPolicySettings):
        return settings
    return ReadPolicySettings(
        default_mode=str(settings["default_mode"]),
        include_global=bool(settings["include_global"]),
        limits_by_mode=settings["limits_by_mode"],
        expand=settings["expand"],
        quotas_by_mode=settings["quotas_by_mode"],
        retrieval=settings["retrieval"],
    )


def get_read_hydration_defaults() -> dict[str, Any]:
    """Return the read defaults expected by CLI hydration."""

    return _coerce_read_policy_settings(get_read_settings()).hydration_defaults()


def get_retrieval_defaults() -> dict[str, float]:
    """Return normalized retrieval defaults for fusion and seed retrieval."""

    return _coerce_read_policy_settings(get_read_settings()).retrieval_defaults()


def resolve_read_limit(*, mode: str, explicit_limit: int | None) -> int:
    """Resolve the effective read limit from explicit payload or mode-based config."""

    if explicit_limit is not None:
        return int(explicit_limit)
    return _coerce_read_policy_settings(get_read_settings()).resolve_limit(mode=mode, explicit_limit=explicit_limit)


def resolve_read_quotas(*, mode: str) -> dict[str, int]:
    """Resolve the configured context-pack quotas for one read mode."""

    return _coerce_read_policy_settings(get_read_settings()).resolve_quotas(mode=mode)


def resolve_read_payload_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve effective read payload defaults from YAML-backed settings."""

    return _coerce_read_policy_settings(get_read_settings()).resolve_payload_defaults(payload)
