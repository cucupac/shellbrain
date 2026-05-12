"""Runtime DB queries for model-usage backfill."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


def load_linked_model_usage_sessions(*, engine: Engine) -> list[dict[str, object]]:
    """Return the latest Shellbrain-linked sync record per repo/host/session."""

    statement = text(
        """
        SELECT DISTINCT ON (repo_id, host_app, host_session_key)
          repo_id,
          host_app,
          host_session_key,
          thread_id,
          episode_id,
          transcript_path
        FROM episode_sync_runs
        WHERE episode_id IS NOT NULL
          AND transcript_path IS NOT NULL
        ORDER BY repo_id, host_app, host_session_key, created_at DESC, id DESC
        """
    )
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(statement).mappings().all()]


def to_linked_session(row: dict[str, Any]) -> dict[str, object]:
    """Keep query rows as JSON-like primitives for the core use case."""

    return {
        "repo_id": row["repo_id"],
        "host_app": row["host_app"],
        "host_session_key": row["host_session_key"],
        "thread_id": row.get("thread_id"),
        "episode_id": row.get("episode_id"),
        "transcript_path": row["transcript_path"],
    }
