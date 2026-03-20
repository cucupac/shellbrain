"""Boot-time helpers for resolving YAML-backed read-policy settings."""

from copy import deepcopy
from typing import Any

from app.boot.config import get_config_provider


_SUPPORTED_MODES = ("targeted", "ambient")
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


def get_read_settings() -> dict[str, Any]:
    """Return normalized read settings from YAML-backed runtime and policy config."""

    config_provider = get_config_provider()
    read_policy = _require_mapping(config_provider.get_read_policy(), field="read_policy")
    runtime = _require_mapping(config_provider.get_runtime(), field="runtime")
    cli_defaults = _require_mapping(runtime.get("cli"), field="runtime.cli")
    limits = _require_mapping(read_policy.get("limits"), field="read_policy.limits")
    expansion = _require_mapping(read_policy.get("expansion"), field="read_policy.expansion")
    quotas = _require_mapping(read_policy.get("quotas"), field="read_policy.quotas")
    weights = _require_mapping(read_policy.get("weights"), field="read_policy.weights")
    fusion = _require_mapping(read_policy.get("fusion"), field="read_policy.fusion")

    settings = {
        "default_mode": _require_mode(cli_defaults.get("default_mode"), field="runtime.cli.default_mode"),
        "include_global": _require_bool(cli_defaults, "include_global", field="runtime.cli"),
        "limits_by_mode": {
            mode: _require_int(limits, mode, field="read_policy.limits")
            for mode in _SUPPORTED_MODES
        },
        "expand": {
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
        "quotas_by_mode": {
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
        "retrieval": {
            "semantic_weight": _require_float(weights, "semantic", field="read_policy.weights"),
            "keyword_weight": _require_float(weights, "keyword", field="read_policy.weights"),
            "k_rrf": _require_float(fusion, "k_rrf", field="read_policy.fusion"),
        },
    }
    return deepcopy(settings)


def get_read_hydration_defaults() -> dict[str, Any]:
    """Return the read defaults expected by CLI hydration."""

    settings = get_read_settings()
    return {
        "default_mode": settings["default_mode"],
        "include_global": settings["include_global"],
        "limits_by_mode": deepcopy(settings["limits_by_mode"]),
        "expand": deepcopy(settings["expand"]),
    }


def get_retrieval_defaults() -> dict[str, float]:
    """Return normalized retrieval defaults for fusion and seed retrieval."""

    return dict(get_read_settings()["retrieval"])


def resolve_read_limit(*, mode: str, explicit_limit: int | None) -> int:
    """Resolve the effective read limit from explicit payload or mode-based config."""

    if explicit_limit is not None:
        return int(explicit_limit)
    settings = get_read_settings()
    resolved_mode = _require_mode(mode, field="read.mode")
    return int(settings["limits_by_mode"][resolved_mode])


def resolve_read_quotas(*, mode: str) -> dict[str, int]:
    """Resolve the configured context-pack quotas for one read mode."""

    settings = get_read_settings()
    resolved_mode = _require_mode(mode, field="read.mode")
    quotas = settings["quotas_by_mode"][resolved_mode]
    return {bucket: int(value) for bucket, value in quotas.items()}


def resolve_read_payload_defaults(payload: dict[str, Any]) -> dict[str, Any]:
    """Resolve effective read payload defaults from YAML-backed settings."""

    settings = get_read_settings()
    resolved = dict(payload)
    mode = resolved.get("mode")
    if mode is None:
        mode = settings["default_mode"]
    resolved["mode"] = _require_mode(mode, field="read.mode")
    if resolved.get("include_global") is None:
        resolved["include_global"] = settings["include_global"]
    if resolved.get("limit") is None:
        resolved["limit"] = settings["limits_by_mode"][resolved["mode"]]

    incoming_expand = resolved.get("expand")
    merged_expand = deepcopy(settings["expand"])
    if incoming_expand is None:
        resolved["expand"] = merged_expand
        return resolved
    if not isinstance(incoming_expand, dict):
        raise ValueError("read.expand must be a mapping")
    for key, value in incoming_expand.items():
        if value is not None:
            merged_expand[key] = value
    resolved["expand"] = merged_expand
    return resolved
