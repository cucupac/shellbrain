"""Boot-time helpers for resolving YAML-backed read-policy settings."""

from copy import deepcopy
from typing import Any

from app.boot.config import get_config_provider


_DEFAULT_LIMITS = {
    "targeted": 8,
    "ambient": 12,
}
_DEFAULT_EXPAND = {
    "semantic_hops": 2,
    "include_problem_links": True,
    "include_fact_update_links": True,
    "include_association_links": True,
    "max_association_depth": 2,
    "min_association_strength": 0.25,
}
_DEFAULT_QUOTAS = {
    "targeted": {"direct": 4, "explicit": 3, "implicit": 1},
    "ambient": {"direct": 4, "explicit": 5, "implicit": 3},
}
_DEFAULT_RETRIEVAL = {
    "semantic_weight": 1.0,
    "keyword_weight": 1.0,
    "k_rrf": 20.0,
}


def get_read_settings() -> dict[str, Any]:
    """Return normalized read settings from YAML-backed runtime and policy config."""

    config_provider = get_config_provider()
    read_policy = config_provider.get_read_policy()
    runtime = config_provider.get_runtime()
    cli_defaults = runtime.get("cli") or {}
    limits = read_policy.get("limits") or {}
    expansion = read_policy.get("expansion") or {}
    quotas = read_policy.get("quotas") or {}
    weights = read_policy.get("weights") or {}
    fusion = read_policy.get("fusion") or {}

    settings = {
        "default_mode": str(cli_defaults.get("default_mode", "targeted")),
        "include_global": bool(cli_defaults.get("include_global", True)),
        "limits_by_mode": {
            mode: int(limits.get(mode, fallback))
            for mode, fallback in _DEFAULT_LIMITS.items()
        },
        "expand": {
            "semantic_hops": int(expansion.get("semantic_hops", _DEFAULT_EXPAND["semantic_hops"])),
            "include_problem_links": bool(
                expansion.get("include_problem_links", _DEFAULT_EXPAND["include_problem_links"])
            ),
            "include_fact_update_links": bool(
                expansion.get("include_fact_update_links", _DEFAULT_EXPAND["include_fact_update_links"])
            ),
            "include_association_links": bool(
                expansion.get("include_association_links", _DEFAULT_EXPAND["include_association_links"])
            ),
            "max_association_depth": int(
                expansion.get("max_association_depth", _DEFAULT_EXPAND["max_association_depth"])
            ),
            "min_association_strength": float(
                expansion.get("min_association_strength", _DEFAULT_EXPAND["min_association_strength"])
            ),
        },
        "quotas_by_mode": {
            mode: {
                bucket: int((quotas.get(mode) or {}).get(bucket, fallback))
                for bucket, fallback in defaults.items()
            }
            for mode, defaults in _DEFAULT_QUOTAS.items()
        },
        "retrieval": {
            "semantic_weight": float(weights.get("semantic", _DEFAULT_RETRIEVAL["semantic_weight"])),
            "keyword_weight": float(weights.get("keyword", _DEFAULT_RETRIEVAL["keyword_weight"])),
            "k_rrf": float(fusion.get("k_rrf", _DEFAULT_RETRIEVAL["k_rrf"])),
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
    return int(settings["limits_by_mode"].get(mode, _DEFAULT_LIMITS["targeted"]))


def resolve_read_quotas(*, mode: str) -> dict[str, int]:
    """Resolve the configured context-pack quotas for one read mode."""

    settings = get_read_settings()
    quotas = settings["quotas_by_mode"].get(mode, settings["quotas_by_mode"]["targeted"])
    return {bucket: int(value) for bucket, value in quotas.items()}
