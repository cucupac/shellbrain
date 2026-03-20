"""Best-effort startup for the repo-local episodic sync poller."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


_PID_FILE = "episode_sync.pid"


def ensure_episode_sync_started(*, repo_id: str, repo_root: Path) -> bool:
    """Start one detached poller process for the repo when needed."""

    runtime_dir = repo_root / ".shellbrain"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    pid_path = runtime_dir / _PID_FILE

    existing_pid = _read_pid(pid_path)
    if existing_pid is not None and _is_running(existing_pid):
        return False

    command = [
        sys.executable,
        "-m",
        "app.periphery.episodes.poller",
        "--repo-id",
        repo_id,
        "--repo-root",
        str(repo_root),
    ]
    process = subprocess.Popen(
        command,
        cwd=repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    pid_path.write_text(json.dumps({"pid": process.pid}), encoding="utf-8")
    return True


def _read_pid(pid_path: Path) -> int | None:
    """Read one stored pid from disk when available."""

    if not pid_path.exists():
        return None
    try:
        payload = json.loads(pid_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    pid = payload.get("pid")
    return int(pid) if isinstance(pid, int) else None


def _is_running(pid: int) -> bool:
    """Return whether one process id is still alive."""

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
