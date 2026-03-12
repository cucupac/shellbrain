"""This module defines CLI hydration helpers that infer missing contextual request fields."""

from pathlib import Path
from typing import Any


def infer_repo_id() -> str:
    """This function infers repo_id from the current working directory name."""

    return Path.cwd().name


def hydrate_read_payload(payload: dict[str, Any], *, inferred_repo_id: str, defaults: dict[str, Any]) -> dict[str, Any]:
    """This function hydrates read payloads with inferred defaults before strict validation."""

    merged = dict(payload)
    merged.setdefault("op", "read")
    merged.setdefault("repo_id", inferred_repo_id)
    merged.setdefault("mode", defaults.get("default_mode", "targeted"))
    merged.setdefault("include_global", defaults.get("include_global", True))
    if "limit" not in merged:
        mode = str(merged["mode"])
        limits_by_mode = defaults.get("limits_by_mode")
        if isinstance(limits_by_mode, dict):
            merged["limit"] = limits_by_mode.get(mode, defaults.get("limit", 20))
        else:
            merged["limit"] = defaults.get("limit", 20)
    expand_defaults = defaults.get("expand")
    if not isinstance(expand_defaults, dict):
        expand_defaults = {
            "semantic_hops": defaults.get("semantic_hops", 2),
            "include_problem_links": defaults.get("include_problem_links", True),
            "include_fact_update_links": defaults.get("include_fact_update_links", True),
            "include_association_links": defaults.get("include_association_links", True),
            "max_association_depth": defaults.get("max_association_depth", 2),
            "min_association_strength": defaults.get("min_association_strength", 0.25),
        }
    incoming_expand = merged.get("expand")
    if isinstance(incoming_expand, dict):
        merged_expand = dict(expand_defaults)
        merged_expand.update(incoming_expand)
        merged["expand"] = merged_expand
    else:
        merged.setdefault("expand", dict(expand_defaults))
    return merged


def hydrate_create_payload(payload: dict[str, Any], *, inferred_repo_id: str, defaults: dict[str, Any]) -> dict[str, Any]:
    """This function hydrates create payloads with inferred scope and confidence defaults."""

    merged = dict(payload)
    merged.setdefault("op", "create")
    merged.setdefault("repo_id", inferred_repo_id)
    if isinstance(merged.get("memory"), dict):
        merged["memory"].setdefault("scope", defaults.get("scope", "repo"))
        merged["memory"].setdefault("confidence", defaults.get("confidence", 0.75))
    return merged


def hydrate_update_payload(payload: dict[str, Any], *, inferred_repo_id: str) -> dict[str, Any]:
    """This function hydrates update payloads with inferred repo and mode defaults."""

    merged = dict(payload)
    merged.setdefault("op", "update")
    merged.setdefault("repo_id", inferred_repo_id)
    merged.setdefault("mode", "commit")
    return merged
