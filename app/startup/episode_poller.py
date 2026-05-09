"""Composition for the repo-local episode poller."""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.process.episode_poller import (
    run_episode_poller as run_infrastructure_episode_poller,
)
from app.startup.use_cases import get_uow_factory


def run_episode_poller(*, repo_id: str, repo_root: Path) -> None:
    """Build dependencies and run the concrete episode poller."""

    run_infrastructure_episode_poller(
        repo_id=repo_id,
        repo_root=repo_root,
        uow_factory=get_uow_factory(),
    )
