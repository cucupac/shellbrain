"""Read-only SQL queries for agent behavior analysis."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


def fetch_agent_behavior_rows(
    *,
    engine: Engine,
    cutoff_at: datetime,
    window_days: int,
) -> dict[str, list[dict[str, object]]]:
    """Return all telemetry rows needed for one pre/post behavior report."""

    if window_days <= 0:
        raise ValueError("window_days must be greater than 0")
    cutoff_at = _coerce_utc(cutoff_at)
    start_at = cutoff_at - timedelta(days=window_days)
    end_at = cutoff_at + timedelta(days=window_days)
    with engine.connect() as conn:
        return {
            "operation_rows": _fetch_operation_rows(
                conn=conn, start_at=start_at, end_at=end_at
            ),
            "read_rows": _fetch_read_rows(conn=conn, start_at=start_at, end_at=end_at),
            "write_rows": _fetch_write_rows(
                conn=conn, start_at=start_at, end_at=end_at
            ),
            "checkpoint_event_rows": _fetch_checkpoint_event_rows(
                conn=conn, start_at=start_at, end_at=end_at
            ),
        }


def _fetch_operation_rows(
    *, conn: Connection, start_at: datetime, end_at: datetime
) -> list[dict[str, object]]:
    """Return operation invocations for the requested window."""

    rows = conn.execute(
        text(
            """
            SELECT
              id,
              command,
              repo_id,
              COALESCE(selected_host_app, 'unknown') AS host_app,
              selected_thread_id AS thread_id,
              guidance_codes,
              total_latency_ms,
              created_at
            FROM operation_invocations
            WHERE created_at >= :start_at
              AND created_at < :end_at
              AND selected_thread_id IS NOT NULL
            ORDER BY created_at ASC, id ASC;
            """
        ),
        {"start_at": start_at, "end_at": end_at},
    ).mappings()
    return [dict(row) for row in rows]


def _fetch_read_rows(
    *, conn: Connection, start_at: datetime, end_at: datetime
) -> list[dict[str, object]]:
    """Return read summaries for the requested window."""

    rows = conn.execute(
        text(
            """
            SELECT
              oi.id AS invocation_id,
              oi.repo_id,
              COALESCE(oi.selected_host_app, 'unknown') AS host_app,
              oi.selected_thread_id AS thread_id,
              oi.total_latency_ms,
              oi.created_at,
              ris.query_text,
              ris.zero_results
            FROM read_invocation_summaries ris
            JOIN operation_invocations oi ON oi.id = ris.invocation_id
            WHERE oi.created_at >= :start_at
              AND oi.created_at < :end_at
              AND oi.selected_thread_id IS NOT NULL
            ORDER BY oi.created_at ASC, oi.id ASC;
            """
        ),
        {"start_at": start_at, "end_at": end_at},
    ).mappings()
    return [dict(row) for row in rows]


def _fetch_write_rows(
    *, conn: Connection, start_at: datetime, end_at: datetime
) -> list[dict[str, object]]:
    """Return successful writes for the requested window."""

    rows = conn.execute(
        text(
            """
            SELECT
              oi.id AS invocation_id,
              oi.command,
              oi.repo_id,
              COALESCE(oi.selected_host_app, 'unknown') AS host_app,
              oi.selected_thread_id AS thread_id,
              oi.total_latency_ms,
              oi.created_at,
              wis.update_type
            FROM write_invocation_summaries wis
            JOIN operation_invocations oi ON oi.id = wis.invocation_id
            WHERE oi.created_at >= :start_at
              AND oi.created_at < :end_at
              AND oi.selected_thread_id IS NOT NULL
            ORDER BY oi.created_at ASC, oi.id ASC;
            """
        ),
        {"start_at": start_at, "end_at": end_at},
    ).mappings()
    return [dict(row) for row in rows]


def _fetch_checkpoint_event_rows(
    *, conn: Connection, start_at: datetime, end_at: datetime
) -> list[dict[str, object]]:
    """Return transcript event rows that may contain SB checkpoints."""

    rows = conn.execute(
        text(
            """
            SELECT
              e.repo_id,
              COALESCE(e.host_app, 'unknown') AS host_app,
              e.thread_id,
              ee.source,
              ee.content,
              ee.created_at
            FROM episode_events ee
            JOIN episodes e ON e.id = ee.episode_id
            WHERE ee.created_at >= :start_at
              AND ee.created_at < :end_at
              AND e.thread_id IS NOT NULL
            ORDER BY ee.created_at ASC, ee.id ASC;
            """
        ),
        {"start_at": start_at, "end_at": end_at},
    ).mappings()
    return [dict(row) for row in rows]


def _coerce_utc(value: object) -> datetime:
    """Return one datetime normalized to UTC."""

    if not isinstance(value, datetime):
        raise TypeError(f"Expected datetime, got {type(value).__name__}")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
