"""Repo registration helpers used around CLI operations."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.local_state import machine_config_store, repo_registration_store


def should_register_repo_during_init(
    *, repo_root: Path, repo_root_arg: str | None, repo_id_arg: str | None
) -> bool:
    """Return whether init should register one repo immediately."""

    if repo_root_arg is not None or repo_id_arg is not None:
        return True
    if repo_registration_store.resolve_git_root(repo_root) is not None:
        return True
    return repo_registration_store.load_repo_registration_for_target(repo_root) is not None


def ensure_repo_registration_for_operation(
    *,
    repo_context=None,
    registration_root: Path | None = None,
    repo_id_override: str | None,
) -> None:
    """Best-effort auto-registration of one repo before a Shellbrain operation."""

    if repo_context is not None:
        registration_root = repo_context.registration_root
    if registration_root is None:
        return
    try:
        machine_config, machine_error = machine_config_store.try_load_machine_config()
        if machine_error is not None or machine_config is None:
            return
        repo_registration_store.register_repo_for_target(
            repo_root=registration_root,
            machine_instance_id=machine_config.machine_instance_id,
            explicit_repo_id=repo_id_override,
        )
    except Exception:
        return
