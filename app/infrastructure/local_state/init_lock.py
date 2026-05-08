"""Machine-scoped lock file mechanics for Shellbrain init."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
import socket
import sys
import time
from typing import Iterator

from app.core.entities.admin_errors import InitLockError
from app.infrastructure.local_state.paths import get_machine_lock_path

_LOCK_TIMEOUT_SECONDS = 30
_STALE_LOCK_MINUTES = 15


@contextmanager
def acquire_init_lock() -> Iterator[None]:
    """Acquire a machine-scoped init lock with stale lock recovery."""

    lock_path = get_machine_lock_path()
    deadline = time.time() + _LOCK_TIMEOUT_SECONDS
    while True:
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            payload = {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "command": " ".join(sys.argv),
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
            try:
                yield
            finally:
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
            return
        except FileExistsError:
            if _clear_stale_lock(lock_path):
                continue
            if time.time() >= deadline:
                holder = _read_lock_holder(lock_path)
                raise InitLockError(
                    f"Shellbrain init is already running for this machine state. Lock holder: {holder or 'unknown'}"
                )
            time.sleep(1)


def _clear_stale_lock(lock_path) -> bool:
    """Remove one stale init lock when the owning process is gone."""

    holder = _read_lock_payload(lock_path)
    if holder is None:
        return False
    started_at = holder.get("started_at")
    pid = holder.get("pid")
    if not isinstance(started_at, str) or not isinstance(pid, int):
        return False
    age = datetime.now(timezone.utc) - datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    if age < timedelta(minutes=_STALE_LOCK_MINUTES):
        return False
    if _pid_exists(pid):
        return False
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return True
    return True


def _pid_exists(pid: int) -> bool:
    """Return whether one process id still exists."""

    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_lock_payload(lock_path) -> dict[str, object] | None:
    """Return parsed lock metadata when available."""

    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _read_lock_holder(lock_path) -> str | None:
    """Return a short human-readable lock holder description."""

    payload = _read_lock_payload(lock_path)
    if payload is None:
        return None
    pid = payload.get("pid")
    hostname = payload.get("hostname")
    command = payload.get("command")
    return f"pid={pid} host={hostname} command={command}"
