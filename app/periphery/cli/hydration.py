"""This module defines CLI hydration helpers that infer missing contextual request fields."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.periphery.admin.repo_state import (
    load_repo_registration_for_target,
    resolve_git_root,
    resolve_repo_identity,
    resolve_registration_root,
)


@dataclass(frozen=True)
class RepoContext:
    """Resolved repository context for one CLI invocation."""

    repo_root: Path
    repo_id: str
    registration_root: Path | None


def infer_repo_id(repo_root: Path) -> str:
    """This function infers repo_id from one resolved repository root."""

    registration = _load_registration_for_root(repo_root)
    if registration is not None:
        return registration.repo_id
    identity = resolve_repo_identity(repo_root=repo_root)
    return identity.repo_id


def resolve_repo_context(*, repo_root_arg: str | None, repo_id_arg: str | None) -> RepoContext:
    """Resolve repo_root and repo_id from explicit CLI flags or the current working directory."""

    repo_root = Path(repo_root_arg).expanduser().resolve() if repo_root_arg else Path.cwd().resolve()
    if not repo_root.exists():
        raise ValueError(f"repo_root does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise ValueError(f"repo_root must be a directory: {repo_root}")
    repo_id = repo_id_arg or infer_repo_id(repo_root)
    registration_root = determine_registration_root(
        repo_root=repo_root,
        explicit_repo_root=repo_root_arg is not None,
        explicit_repo_id=repo_id_arg is not None,
    )
    return RepoContext(repo_root=repo_root, repo_id=repo_id, registration_root=registration_root)


def determine_registration_root(*, repo_root: Path, explicit_repo_root: bool, explicit_repo_id: bool) -> Path | None:
    """Return the root that should auto-register on first real use, when any."""

    target = Path(repo_root).resolve()
    if load_repo_registration_for_target(target) is not None:
        return resolve_registration_root(target)
    git_root = resolve_git_root(target)
    if git_root is not None:
        return git_root
    if explicit_repo_root or explicit_repo_id:
        return target
    return None


def _load_registration_for_root(repo_root: Path):
    """Return a repo registration from the target root or its git root."""

    return load_repo_registration_for_target(repo_root)


def hydrate_read_payload(payload: dict[str, Any], *, inferred_repo_id: str, defaults: dict[str, Any]) -> dict[str, Any]:
    """This function hydrates read payloads with inferred defaults before strict validation."""

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
            raise ValueError(f"read hydration defaults must define limit for mode: {mode}")
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


def hydrate_create_payload(payload: dict[str, Any], *, inferred_repo_id: str, defaults: dict[str, Any]) -> dict[str, Any]:
    """This function hydrates create payloads with inferred scope defaults."""

    if "scope" not in defaults:
        raise ValueError("create hydration defaults must include scope")
    merged = dict(payload)
    merged.setdefault("op", "create")
    merged.setdefault("repo_id", inferred_repo_id)
    if isinstance(merged.get("memory"), dict):
        merged["memory"].setdefault("scope", defaults["scope"])
    return merged


def hydrate_events_payload(payload: dict[str, Any], *, inferred_repo_id: str) -> dict[str, Any]:
    """This function hydrates events payloads with inferred repo defaults."""

    merged = dict(payload)
    merged.setdefault("op", "events")
    merged.setdefault("repo_id", inferred_repo_id)
    merged.setdefault("limit", 20)
    return merged


def hydrate_update_payload(payload: dict[str, Any], *, inferred_repo_id: str) -> dict[str, Any]:
    """This function hydrates update payloads with inferred repo defaults."""

    merged = dict(payload)
    merged.setdefault("op", "update")
    merged.setdefault("repo_id", inferred_repo_id)
    return merged


def hydrate_concept_payload(payload: dict[str, Any], *, inferred_repo_id: str) -> dict[str, Any]:
    """Hydrate concept endpoint payloads with inferred repo defaults."""

    merged = dict(payload)
    merged.setdefault("repo_id", inferred_repo_id)
    return merged
