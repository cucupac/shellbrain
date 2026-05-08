"""Repo-local status file storage for episode sync."""

from __future__ import annotations

import json
from pathlib import Path


def record_episode_sync_status(
    *,
    repo_root: Path,
    host_app: str,
    host_session_key: str,
    last_successful_sync_at: str | None,
    last_error: str | None,
) -> None:
    """Write one small repo-local health/status file."""

    runtime_dir = repo_root / ".shellbrain"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    status_path = runtime_dir / "episode_sync_status.json"
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        status = {"repo_root": str(repo_root), "hosts": {}}

    hosts = status.setdefault("hosts", {})
    host_status = hosts.setdefault(host_app, {})
    host_status["current_session_key"] = host_session_key
    if last_successful_sync_at is not None:
        host_status["last_successful_sync_at"] = last_successful_sync_at
    host_status["last_error"] = last_error
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")
