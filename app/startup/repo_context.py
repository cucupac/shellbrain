"""Repository context resolution for entrypoint invocations."""

from dataclasses import dataclass
from pathlib import Path

from app.infrastructure.local_state.repo_registration_store import (
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


def resolve_repo_context(
    *, repo_root_arg: str | None, repo_id_arg: str | None
) -> RepoContext:
    """Resolve repo_root and repo_id from explicit CLI flags or the current working directory."""

    repo_root = (
        Path(repo_root_arg).expanduser().resolve()
        if repo_root_arg
        else Path.cwd().resolve()
    )
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
    return RepoContext(
        repo_root=repo_root, repo_id=repo_id, registration_root=registration_root
    )


def determine_registration_root(
    *, repo_root: Path, explicit_repo_root: bool, explicit_repo_id: bool
) -> Path | None:
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
