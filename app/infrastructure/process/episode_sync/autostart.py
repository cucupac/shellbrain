"""Best-effort episode sync process autostart behavior."""

from __future__ import annotations


def maybe_start_sync(repo_context, *, ensure_episode_sync_started) -> bool:
    """Best-effort startup for repo-local episode sync after a successful command."""

    try:
        return bool(
            ensure_episode_sync_started(
                repo_id=repo_context.repo_id,
                repo_root=repo_context.repo_root,
            )
        )
    except Exception:
        return False
