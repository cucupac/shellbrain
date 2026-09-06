"""Read-only query helpers for the admin analytics report."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection


def fetch_operation_invocations(
    *, conn: Connection, start_at: datetime
) -> list[dict[str, object]]:
    """Return operation invocations inside the reporting window."""

    rows = conn.execute(
        text(
            """
            SELECT
              id,
              command,
              repo_id,
              selected_host_app,
              selected_thread_id,
              outcome,
              error_stage,
              error_code,
              error_message,
              total_latency_ms,
              selection_ambiguous,
              guidance_codes,
              created_at
            FROM operation_invocations
            WHERE created_at >= :start_at
            ORDER BY created_at ASC, id ASC;
            """
        ),
        {"start_at": start_at},
    ).mappings()
    return [dict(row) for row in rows]


def fetch_read_summaries(
    *, conn: Connection, start_at: datetime
) -> list[dict[str, object]]:
    """Return read summaries inside the reporting window."""

    rows = conn.execute(
        text(
            """
            SELECT
              oi.id AS invocation_id,
              oi.repo_id,
              oi.selected_thread_id,
              oi.created_at,
              ris.zero_results
            FROM read_invocation_summaries ris
            JOIN operation_invocations oi ON oi.id = ris.invocation_id
            WHERE oi.created_at >= :start_at
            UNION ALL
            SELECT oi.id AS invocation_id, oi.repo_id, oi.selected_thread_id,
                   oi.created_at, (rs.fallback_reason = 'no_candidates') IS TRUE AS zero_results
            FROM recall_invocation_summaries rs
            JOIN operation_invocations oi ON oi.id = rs.invocation_id
            WHERE oi.created_at >= :start_at
            ORDER BY created_at ASC, invocation_id ASC;
            """
        ),
        {"start_at": start_at},
    ).mappings()
    return [dict(row) for row in rows]


def fetch_sync_runs(*, conn: Connection, start_at: datetime) -> list[dict[str, object]]:
    """Return sync runs inside the reporting window."""

    rows = conn.execute(
        text(
            """
            SELECT
              id,
              repo_id,
              host_app,
              thread_id,
              outcome,
              error_stage,
              error_message,
              imported_event_count,
              created_at
            FROM episode_sync_runs
            WHERE created_at >= :start_at
            ORDER BY created_at ASC, id ASC;
            """
        ),
        {"start_at": start_at},
    ).mappings()
    return [dict(row) for row in rows]
