"""Repo-local registration and identity helpers for Shellbrain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib
from typing import Any


REPO_STATE_VERSION = 1
IDENTITY_STRENGTH_EXPLICIT = "explicit"
IDENTITY_STRENGTH_GIT_REMOTE = "git_remote"
IDENTITY_STRENGTH_WEAK_LOCAL = "weak_local"


@dataclass(frozen=True)
class RepoRegistration:
    """Repo-local registration metadata bound to one machine instance."""

    repo_state_version: int
    repo_id: str
    identity_strength: str
    git_root: str | None
    source_remote: str | None
    registered_at: str
    machine_instance_id: str
    claude_status: str
    claude_settings_path: str | None = None
    claude_note: str | None = None


@dataclass(frozen=True)
class RepoIdentity:
    """Resolved repo identity before registration."""

    repo_id: str
    identity_strength: str
    git_root: str | None
    source_remote: str | None


def repo_runtime_dir(repo_root: Path) -> Path:
    """Return the repo-local runtime directory."""

    return Path(repo_root).resolve() / ".shellbrain"


def repo_registration_path(repo_root: Path) -> Path:
    """Return the repo-local registration file path."""

    return repo_runtime_dir(repo_root) / "repo_registration.toml"


def resolve_registration_root(repo_root: Path) -> Path:
    """Return the canonical directory where repo registration should live."""

    target = Path(repo_root).resolve()
    git_root = resolve_git_root(target)
    return git_root or target


def load_repo_registration(repo_root: Path) -> RepoRegistration | None:
    """Load one repo registration when present."""

    path = repo_registration_path(repo_root)
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(payload, dict):
        raise ValueError("Repo registration must be a TOML table.")
    return RepoRegistration(
        repo_state_version=int(payload.get("repo_state_version") or 0),
        repo_id=_required_str(payload, "repo_id"),
        identity_strength=_required_str(payload, "identity_strength"),
        git_root=_optional_str(payload.get("git_root")),
        source_remote=_optional_str(payload.get("source_remote")),
        registered_at=_required_str(payload, "registered_at"),
        machine_instance_id=_required_str(payload, "machine_instance_id"),
        claude_status=_required_str(payload, "claude_status"),
        claude_settings_path=_optional_str(payload.get("claude_settings_path")),
        claude_note=_optional_str(payload.get("claude_note")),
    )


def load_repo_registration_for_target(repo_root: Path) -> RepoRegistration | None:
    """Load one repo registration from the canonical target root."""

    target = Path(repo_root).resolve()
    registration_root = resolve_registration_root(target)
    registration = load_repo_registration(registration_root)
    if registration is not None:
        return registration
    if registration_root != target:
        return None
    return load_repo_registration(target)


def save_repo_registration(registration: RepoRegistration, repo_root: Path) -> Path:
    """Persist one repo registration."""

    path = repo_registration_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"repo_state_version = {registration.repo_state_version}",
        f"repo_id = {json.dumps(registration.repo_id)}",
        f"identity_strength = {json.dumps(registration.identity_strength)}",
        f"git_root = {json.dumps(registration.git_root or '')}",
        f"source_remote = {json.dumps(registration.source_remote or '')}",
        f"registered_at = {json.dumps(registration.registered_at)}",
        f"machine_instance_id = {json.dumps(registration.machine_instance_id)}",
        f"claude_status = {json.dumps(registration.claude_status)}",
        f"claude_settings_path = {json.dumps(registration.claude_settings_path or '')}",
        f"claude_note = {json.dumps(registration.claude_note or '')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def register_repo(
    *,
    repo_root: Path,
    machine_instance_id: str,
    explicit_repo_id: str | None = None,
    claude_status: str = "not_checked",
    claude_settings_path: str | None = None,
    claude_note: str | None = None,
) -> RepoRegistration:
    """Resolve and persist one repo registration."""

    identity = resolve_repo_identity(repo_root=repo_root, explicit_repo_id=explicit_repo_id)
    registration_root = Path(identity.git_root).resolve() if identity.git_root is not None else Path(repo_root).resolve()
    registration = RepoRegistration(
        repo_state_version=REPO_STATE_VERSION,
        repo_id=identity.repo_id,
        identity_strength=identity.identity_strength,
        git_root=identity.git_root,
        source_remote=identity.source_remote,
        registered_at=datetime.now(timezone.utc).isoformat(),
        machine_instance_id=machine_instance_id,
        claude_status=claude_status,
        claude_settings_path=claude_settings_path,
        claude_note=claude_note,
    )
    save_repo_registration(registration, registration_root)
    return registration


def register_repo_for_target(
    *,
    repo_root: Path,
    machine_instance_id: str,
    explicit_repo_id: str | None = None,
) -> tuple[RepoRegistration, bool]:
    """Register one target repo idempotently and return whether the file changed."""

    target = Path(repo_root).resolve()
    identity = resolve_repo_identity(repo_root=target, explicit_repo_id=explicit_repo_id)
    registration_root = Path(identity.git_root).resolve() if identity.git_root is not None else target
    existing = load_repo_registration(registration_root)
    claude_status = existing.claude_status if existing is not None else "not_checked"
    claude_settings_path = existing.claude_settings_path if existing is not None else None
    claude_note = existing.claude_note if existing is not None else None
    if existing is not None and _registration_matches(
        existing=existing,
        identity=identity,
        machine_instance_id=machine_instance_id,
        claude_status=claude_status,
        claude_settings_path=claude_settings_path,
        claude_note=claude_note,
    ):
        return existing, False
    registration = RepoRegistration(
        repo_state_version=REPO_STATE_VERSION,
        repo_id=identity.repo_id,
        identity_strength=identity.identity_strength,
        git_root=identity.git_root,
        source_remote=identity.source_remote,
        registered_at=datetime.now(timezone.utc).isoformat(),
        machine_instance_id=machine_instance_id,
        claude_status=claude_status,
        claude_settings_path=claude_settings_path,
        claude_note=claude_note,
    )
    save_repo_registration(registration, registration_root)
    return registration, True


def resolve_repo_identity(*, repo_root: Path, explicit_repo_id: str | None = None) -> RepoIdentity:
    """Resolve repo identity using explicit override, git remotes, or weak local fallback."""

    target = Path(repo_root).resolve()
    if explicit_repo_id:
        git_root = resolve_git_root(target)
        return RepoIdentity(
            repo_id=explicit_repo_id,
            identity_strength=IDENTITY_STRENGTH_EXPLICIT,
            git_root=str(git_root) if git_root is not None else None,
            source_remote=None,
        )
    git_root = resolve_git_root(target)
    if git_root is not None:
        remotes = list_git_remotes(git_root)
        if "origin" in remotes:
            return RepoIdentity(
                repo_id=normalize_git_remote(remotes["origin"]),
                identity_strength=IDENTITY_STRENGTH_GIT_REMOTE,
                git_root=str(git_root),
                source_remote="origin",
            )
        if len(remotes) == 1:
            remote_name, remote_url = next(iter(remotes.items()))
            return RepoIdentity(
                repo_id=normalize_git_remote(remote_url),
                identity_strength=IDENTITY_STRENGTH_GIT_REMOTE,
                git_root=str(git_root),
                source_remote=remote_name,
            )
        if len(remotes) > 1:
            raise ValueError(
                "Multiple git remotes are configured and none is named origin. Rerun with --repo-id to choose a durable Shellbrain repo identity."
            )
    return RepoIdentity(
        repo_id=f"{target.name}::{_weak_local_hash(target)}",
        identity_strength=IDENTITY_STRENGTH_WEAK_LOCAL,
        git_root=str(git_root) if git_root is not None else None,
        source_remote=None,
    )


def resolve_git_root(repo_root: Path) -> Path | None:
    """Return the git root when the target directory is inside one repository."""

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    output = completed.stdout.strip()
    if not output:
        return None
    return Path(output).expanduser().resolve()


def list_git_remotes(repo_root: Path) -> dict[str, str]:
    """Return fetch remotes keyed by remote name."""

    try:
        completed = subprocess.run(
            ["git", "remote", "-v"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return {}
    if completed.returncode != 0:
        return {}
    remotes: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[2] != "(fetch)":
            continue
        remotes.setdefault(parts[0], parts[1])
    return remotes


def normalize_git_remote(url: str) -> str:
    """Normalize one git remote into a stable host/owner/repo identity."""

    value = url.strip()
    if not value:
        raise ValueError("Git remote URL must not be empty.")
    scp_match = re.match(r"^(?:[^@]+@)?([^:]+):(.+)$", value)
    if scp_match and "://" not in value:
        host = scp_match.group(1).lower()
        path = scp_match.group(2)
    else:
        from urllib.parse import urlparse

        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        path = parsed.path.lstrip("/")
    normalized_path = path.removesuffix(".git").strip("/")
    if not host or not normalized_path:
        raise ValueError(f"Unsupported git remote URL: {url}")
    return f"{host}/{normalized_path}"


def _required_str(payload: dict[str, Any], key: str) -> str:
    """Return a required string field."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Repo registration field {key!r} must be a non-empty string.")
    return value


def _optional_str(value: Any) -> str | None:
    """Return an optional string field."""

    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Optional repo registration fields must be strings when present.")
    return value or None


def _weak_local_hash(path: Path) -> str:
    """Return one short weak-local identity suffix."""

    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()
    return digest[:12]


def _registration_matches(
    *,
    existing: RepoRegistration,
    identity: RepoIdentity,
    machine_instance_id: str,
    claude_status: str,
    claude_settings_path: str | None,
    claude_note: str | None,
) -> bool:
    """Return whether one existing registration already matches the desired state."""

    return (
        existing.repo_state_version == REPO_STATE_VERSION
        and existing.repo_id == identity.repo_id
        and existing.identity_strength == identity.identity_strength
        and existing.git_root == identity.git_root
        and existing.source_remote == identity.source_remote
        and existing.machine_instance_id == machine_instance_id
        and existing.claude_status == claude_status
        and existing.claude_settings_path == claude_settings_path
        and existing.claude_note == claude_note
    )
