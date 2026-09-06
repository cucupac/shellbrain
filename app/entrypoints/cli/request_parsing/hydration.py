"""Pure request hydration helpers for agent-facing contracts."""

from __future__ import annotations

from typing import Any


def hydrate_read_payload(
    payload: dict[str, Any], *, inferred_repo_id: str, defaults: dict[str, Any]
) -> dict[str, Any]:
    """Hydrate read payloads with inferred defaults before strict validation."""

    return {"op": "read", "repo_id": inferred_repo_id, **defaults, **payload}


def hydrate_memory_add_payload(
    payload: dict[str, Any], *, inferred_repo_id: str
) -> dict[str, Any]:
    """Hydrate create payloads with the repository identity."""

    merged = dict(payload)
    merged.setdefault("op", "create")
    merged.setdefault("repo_id", inferred_repo_id)
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


def hydrate_repo_id(
    payload: dict[str, Any], *, inferred_repo_id: str
) -> dict[str, Any]:
    """Default `repo_id` to the inferred repo when the payload omits it."""

    merged = dict(payload)
    merged.setdefault("repo_id", inferred_repo_id)
    return merged
