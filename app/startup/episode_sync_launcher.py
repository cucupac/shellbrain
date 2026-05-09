"""Composition wrapper for repo-local episode sync poller startup."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.process.episode_sync_launcher import (
    ensure_episode_sync_started as launch_episode_sync_process,
)

EPISODE_SYNC_ENTRYPOINT_MODULE = "app.entrypoints.jobs.episode_sync"


def ensure_episode_sync_started(*, repo_id: str, repo_root: Path) -> bool:
    """Start one detached poller process for the repo when needed."""

    return launch_episode_sync_process(
        repo_id=repo_id,
        repo_root=repo_root,
        module_name=EPISODE_SYNC_ENTRYPOINT_MODULE,
    )
