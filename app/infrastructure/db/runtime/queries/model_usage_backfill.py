"""Runtime DB queries for model-usage backfill."""

from __future__ import annotations

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
