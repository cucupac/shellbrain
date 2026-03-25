"""Repo-local singleton lock helpers for the episode poller."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket


_LOCK_DIR_NAME = "episode_sync.lock"
_OWNER_FILENAME = "owner.json"
_PID_FILENAME = "episode_sync.pid"


@dataclass(frozen=True)
class PollerLockInspection:
    """Current status of the repo-local poller singleton lock."""

    lock_root: Path
    owner_path: Path
    status: str
    owner: dict[str, object] | None

    @property
    def active(self) -> bool:
        """Return whether the lock currently belongs to a live owner."""

        return self.status in {"active", "foreign_active"}


@dataclass
class PollerLockHandle:
    """Lease for one acquired poller lock."""

    repo_root: Path
    lock_root: Path
    owner_path: Path
    owner: dict[str, object]
    released: bool = False

    def release(self) -> None:
        """Release the repo-local lock when still owned by this process."""

        if self.released:
            return
        release_poller_lock(self)
        self.released = True


def inspect_poller_lock(*, repo_root: Path) -> PollerLockInspection:
    """Inspect the current poller singleton lock for one repo root."""

    resolved_repo_root = repo_root.resolve()
    lock_root = _lock_root(resolved_repo_root)
    owner_path = lock_root / _OWNER_FILENAME
    if not lock_root.exists():
        return PollerLockInspection(lock_root=lock_root, owner_path=owner_path, status="unlocked", owner=None)
    if not lock_root.is_dir():
        return PollerLockInspection(lock_root=lock_root, owner_path=owner_path, status="stale", owner=None)

    owner = _read_owner_payload(owner_path)
    if owner is None or not _owner_payload_is_well_formed(owner=owner, repo_root=resolved_repo_root):
        return PollerLockInspection(lock_root=lock_root, owner_path=owner_path, status="stale", owner=owner)

    hostname = str(owner["hostname"])
    if hostname != _current_hostname():
        return PollerLockInspection(lock_root=lock_root, owner_path=owner_path, status="foreign_active", owner=owner)

    pid = int(owner["pid"])
    if _is_process_running(pid):
        return PollerLockInspection(lock_root=lock_root, owner_path=owner_path, status="active", owner=owner)
    return PollerLockInspection(lock_root=lock_root, owner_path=owner_path, status="stale", owner=owner)


def acquire_poller_lock(*, repo_id: str, repo_root: Path) -> PollerLockHandle | None:
    """Acquire the repo-local singleton lock, returning None when another owner is active."""

    resolved_repo_root = repo_root.resolve()
    runtime_dir = resolved_repo_root / ".shellbrain"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    lock_root = _lock_root(resolved_repo_root)
    owner_path = lock_root / _OWNER_FILENAME
    owner = _build_owner_payload(repo_id=repo_id, repo_root=resolved_repo_root)

    for _attempt in range(2):
        try:
            lock_root.mkdir()
        except FileExistsError:
            inspection = inspect_poller_lock(repo_root=resolved_repo_root)
            if inspection.active:
                return None
            if inspection.status == "stale":
                _remove_stale_lock(lock_root=lock_root, expected_owner=inspection.owner)
                continue
            return None

        try:
            owner_path.write_text(json.dumps(owner, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            _remove_path(lock_root)
            raise
        return PollerLockHandle(
            repo_root=resolved_repo_root,
            lock_root=lock_root,
            owner_path=owner_path,
            owner=owner,
        )

    return None


def release_poller_lock(handle: PollerLockHandle) -> None:
    """Release the singleton lock when the on-disk owner still matches this handle."""

    inspection = inspect_poller_lock(repo_root=handle.repo_root)
    if inspection.status == "unlocked":
        return
    if inspection.owner != handle.owner:
        return

    try:
        handle.owner_path.unlink(missing_ok=True)
    except OSError:
        return
    try:
        handle.lock_root.rmdir()
    except OSError:
        return


def write_poller_pid_artifact(*, repo_root: Path) -> Path:
    """Persist the compatibility pid artifact for the current poller process."""

    resolved_repo_root = repo_root.resolve()
    runtime_dir = resolved_repo_root / ".shellbrain"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    pid_path = runtime_dir / _PID_FILENAME
    pid_path.write_text(json.dumps({"pid": os.getpid()}, indent=2, sort_keys=True), encoding="utf-8")
    return pid_path


def _lock_root(repo_root: Path) -> Path:
    """Return the canonical lock directory path for one repo root."""

    return repo_root / ".shellbrain" / _LOCK_DIR_NAME


def _build_owner_payload(*, repo_id: str, repo_root: Path) -> dict[str, object]:
    """Build the owner metadata stored inside the singleton lock."""

    return {
        "hostname": _current_hostname(),
        "pid": os.getpid(),
        "repo_id": repo_id,
        "repo_root": str(repo_root),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def _read_owner_payload(owner_path: Path) -> dict[str, object] | None:
    """Read the owner metadata for one existing lock when present."""

    try:
        payload = json.loads(owner_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, NotADirectoryError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _owner_payload_is_well_formed(*, owner: dict[str, object], repo_root: Path) -> bool:
    """Return whether one owner payload is usable for lock inspection."""

    return (
        isinstance(owner.get("pid"), int)
        and isinstance(owner.get("hostname"), str)
        and bool(str(owner.get("hostname")))
        and isinstance(owner.get("repo_id"), str)
        and owner.get("repo_root") == str(repo_root)
        and isinstance(owner.get("started_at"), str)
    )


def _remove_stale_lock(*, lock_root: Path, expected_owner: dict[str, object] | None) -> None:
    """Remove one stale lock only when the current stale owner still matches the expected state."""

    if not lock_root.exists():
        return
    inspection = inspect_poller_lock(repo_root=lock_root.parent.parent)
    if inspection.status != "stale":
        return
    if expected_owner is not None and inspection.owner != expected_owner:
        return
    _remove_path(lock_root)


def _remove_path(path: Path) -> None:
    """Remove one filesystem path whether it is a file or directory."""

    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
        return
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _current_hostname() -> str:
    """Return the normalized current hostname for lock ownership checks."""

    return socket.gethostname().strip().lower()


def _is_process_running(pid: int) -> bool:
    """Return whether one pid is currently alive on this host."""

    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True
