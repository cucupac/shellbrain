"""Detached process launcher for the repo-local episode sync poller."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from app.infrastructure.local_state.poller_lock import inspect_poller_lock


def ensure_episode_sync_started(*, repo_id: str, repo_root: Path) -> bool:
    """Start one detached poller process for the repo when needed."""

    resolved_repo_root = repo_root.resolve()
    inspection = inspect_poller_lock(repo_root=resolved_repo_root)
    if inspection.active:
        return False

    command = [
        sys.executable,
        "-m",
        "app.entrypoints.jobs.episode_sync",
        "--repo-id",
        repo_id,
        "--repo-root",
        str(resolved_repo_root),
    ]
    subprocess.Popen(
        command,
        cwd=resolved_repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True
