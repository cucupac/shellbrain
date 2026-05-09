"""Pure request hydration helpers for agent-facing contracts."""

from __future__ import annotations

from typing import Any


def hydrate_read_payload(
    payload: dict[str, Any], *, inferred_repo_id: str, defaults: dict[str, Any]
) -> dict[str, Any]:
    """Hydrate read payloads with inferred defaults before strict validation."""

    if not isinstance(defaults.get("limits_by_mode"), dict):
        raise ValueError("read hydration defaults must include limits_by_mode")
    if not isinstance(defaults.get("expand"), dict):
        raise ValueError("read hydration defaults must include expand")
    if "default_mode" not in defaults:
        raise ValueError("read hydration defaults must include default_mode")
    if "include_global" not in defaults:
        raise ValueError("read hydration defaults must include include_global")

    merged = dict(payload)
    merged.setdefault("op", "read")
    merged.setdefault("repo_id", inferred_repo_id)
    merged.setdefault("mode", defaults["default_mode"])
    merged.setdefault("include_global", defaults["include_global"])
    if "limit" not in merged:
        mode = str(merged["mode"])
        limits_by_mode = defaults["limits_by_mode"]
        if mode not in limits_by_mode:
            raise ValueError(
                f"read hydration defaults must define limit for mode: {mode}"
            )
        merged["limit"] = limits_by_mode[mode]
    expand_defaults = dict(defaults["expand"])
    incoming_expand = merged.get("expand")
    if isinstance(incoming_expand, dict):
        merged_expand = dict(expand_defaults)
        merged_expand.update(incoming_expand)
        merged["expand"] = merged_expand
    else:
        merged.setdefault("expand", dict(expand_defaults))
    return merged


def hydrate_memory_add_payload(
    payload: dict[str, Any], *, inferred_repo_id: str, defaults: dict[str, Any]
) -> dict[str, Any]:
    """Hydrate create payloads with inferred scope defaults."""

    if "scope" not in defaults:
        raise ValueError("create hydration defaults must include scope")
    merged = dict(payload)
    merged.setdefault("op", "create")
    merged.setdefault("repo_id", inferred_repo_id)
    if isinstance(merged.get("memory"), dict):
        merged["memory"].setdefault("scope", defaults["scope"])
    return merged


def hydrate_events_payload(
    payload: dict[str, Any], *, inferred_repo_id: str
) -> dict[str, Any]:
    """Hydrate events payloads with inferred repo defaults."""

    merged = dict(payload)
    merged.setdefault("op", "events")
    merged.setdefault("repo_id", inferred_repo_id)
    merged.setdefault("limit", 20)
    return merged


def hydrate_update_payload(
    payload: dict[str, Any], *, inferred_repo_id: str
) -> dict[str, Any]:
    """Hydrate update payloads with inferred repo defaults."""

    merged = dict(payload)
    merged.setdefault("op", "update")
    merged.setdefault("repo_id", inferred_repo_id)
    return merged


def hydrate_concept_add_payload(
    payload: dict[str, Any], *, inferred_repo_id: str
) -> dict[str, Any]:
    """Hydrate concept-add payloads with inferred repo defaults."""

    merged = dict(payload)
    merged.setdefault("repo_id", inferred_repo_id)
    return merged


def hydrate_concept_update_payload(
    payload: dict[str, Any], *, inferred_repo_id: str
) -> dict[str, Any]:
    """Hydrate concept-update payloads with inferred repo defaults."""

    merged = dict(payload)
    merged.setdefault("repo_id", inferred_repo_id)
    return merged


def hydrate_concept_show_payload(
    payload: dict[str, Any], *, inferred_repo_id: str
) -> dict[str, Any]:
    """Hydrate concept-show payloads with inferred repo defaults."""

    merged = dict(payload)
    merged.setdefault("repo_id", inferred_repo_id)
    return merged
