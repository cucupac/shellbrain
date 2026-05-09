"""SQL query helpers for repo-scoped Shellbrain metrics snapshots."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Connection


def fetch_metrics_repo_ids(*, conn: Connection) -> list[str]:
    """Return all repo identifiers that have metrics-relevant telemetry."""

    rows = conn.execute(
        text(
            """
            SELECT repo_id
            FROM (
              SELECT DISTINCT repo_id FROM operation_invocations
              UNION
              SELECT DISTINCT repo_id FROM memories
              UNION
              SELECT DISTINCT repo_id FROM episode_sync_runs
            ) repo_ids
            WHERE repo_id IS NOT NULL
              AND repo_id <> ''
            ORDER BY repo_id ASC;
            """
        )
    ).mappings()
    return [str(row["repo_id"]) for row in rows]


def fetch_daily_utility_rows(
    *,
    conn: Connection,
    repo_id: str,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, object]]:
    """Return daily utility vote aggregates for one repo and time range."""

    rows = conn.execute(
        text(
            """
            SELECT
              date_trunc('day', u.created_at AT TIME ZONE 'UTC') AS day_utc,
              COUNT(*)::INTEGER AS vote_count,
              COALESCE(SUM(u.vote), 0)::DOUBLE PRECISION AS vote_sum
            FROM utility_observations u
            JOIN memories problem_mem ON problem_mem.id = u.problem_id
            WHERE problem_mem.repo_id = :repo_id
              AND u.created_at >= :start_at
              AND u.created_at < :end_at
            GROUP BY date_trunc('day', u.created_at AT TIME ZONE 'UTC')
            ORDER BY day_utc ASC;
            """
        ),
        {"repo_id": repo_id, "start_at": start_at, "end_at": end_at},
    ).mappings()
    return [dict(row) for row in rows]


def fetch_daily_followthrough_rows(
    *,
    conn: Connection,
    repo_id: str,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, object]]:
    """Return daily utility-guidance follow-through counts for one repo and time range."""

    rows = conn.execute(
        text(
            """
            WITH pending_threads AS (
              SELECT
                oi.repo_id,
                oi.selected_thread_id,
                MIN(oi.created_at) AS first_guidance_at
              FROM operation_invocations oi
              WHERE oi.repo_id = :repo_id
                AND oi.created_at >= :start_at
                AND oi.created_at < :end_at
                AND oi.selected_thread_id IS NOT NULL
                AND oi.guidance_codes @> '["pending_utility_votes"]'::jsonb
              GROUP BY oi.repo_id, oi.selected_thread_id
            ),
            vote_threads AS (
              SELECT
                oi.repo_id,
                oi.selected_thread_id,
                MIN(oi.created_at) AS first_vote_at
              FROM write_invocation_summaries wis
              JOIN operation_invocations oi ON oi.id = wis.invocation_id
              WHERE oi.repo_id = :repo_id
                AND oi.created_at >= :start_at
                AND oi.created_at < :end_at
                AND oi.selected_thread_id IS NOT NULL
                AND wis.update_type IN ('utility_vote', 'utility_vote_batch')
              GROUP BY oi.repo_id, oi.selected_thread_id
            )
            SELECT
              date_trunc('day', pending.first_guidance_at AT TIME ZONE 'UTC') AS day_utc,
              COUNT(*)::INTEGER AS opportunity_count,
              COUNT(*) FILTER (
                WHERE votes.first_vote_at IS NOT NULL
                  AND votes.first_vote_at > pending.first_guidance_at
              )::INTEGER AS followthrough_count
            FROM pending_threads pending
            LEFT JOIN vote_threads votes
              ON votes.repo_id = pending.repo_id
             AND votes.selected_thread_id = pending.selected_thread_id
            GROUP BY date_trunc('day', pending.first_guidance_at AT TIME ZONE 'UTC')
            ORDER BY day_utc ASC;
            """
        ),
        {"repo_id": repo_id, "start_at": start_at, "end_at": end_at},
    ).mappings()
    return [dict(row) for row in rows]


def fetch_daily_zero_result_rows(
    *,
    conn: Connection,
    repo_id: str,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, object]]:
    """Return daily read and zero-result counts for one repo and time range."""

    rows = conn.execute(
        text(
            """
            SELECT
              date_trunc('day', oi.created_at AT TIME ZONE 'UTC') AS day_utc,
              COUNT(*)::INTEGER AS read_count,
              COUNT(*) FILTER (WHERE ris.zero_results)::INTEGER AS zero_result_count
            FROM read_invocation_summaries ris
            JOIN operation_invocations oi ON oi.id = ris.invocation_id
            WHERE oi.repo_id = :repo_id
              AND oi.created_at >= :start_at
              AND oi.created_at < :end_at
            GROUP BY date_trunc('day', oi.created_at AT TIME ZONE 'UTC')
            ORDER BY day_utc ASC;
            """
        ),
        {"repo_id": repo_id, "start_at": start_at, "end_at": end_at},
    ).mappings()
    return [dict(row) for row in rows]


def fetch_daily_events_before_write_rows(
    *,
    conn: Connection,
    repo_id: str,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, object]]:
    """Return daily write counts and events-before-write compliance for one repo."""

    rows = conn.execute(
        text(
            """
            SELECT
              date_trunc('day', oi.created_at AT TIME ZONE 'UTC') AS day_utc,
              COUNT(*)::INTEGER AS write_count,
              COUNT(*) FILTER (
                WHERE EXISTS (
                  SELECT 1
                  FROM operation_invocations prior_events
                  WHERE prior_events.repo_id = oi.repo_id
                    AND prior_events.selected_thread_id = oi.selected_thread_id
                    AND prior_events.command = 'events'
                    AND prior_events.created_at < oi.created_at
                )
              )::INTEGER AS compliant_count
            FROM write_invocation_summaries wis
            JOIN operation_invocations oi ON oi.id = wis.invocation_id
            WHERE oi.repo_id = :repo_id
              AND oi.created_at >= :start_at
              AND oi.created_at < :end_at
            GROUP BY date_trunc('day', oi.created_at AT TIME ZONE 'UTC')
            ORDER BY day_utc ASC;
            """
        ),
        {"repo_id": repo_id, "start_at": start_at, "end_at": end_at},
    ).mappings()
    return [dict(row) for row in rows]


def fetch_sync_health_summary(
    *,
    conn: Connection,
    repo_id: str,
    start_at: datetime,
    end_at: datetime,
) -> dict[str, object]:
    """Return current-window sync health counts for one repo."""

    row = (
        conn.execute(
            text(
                """
            SELECT
              COUNT(*)::INTEGER AS sync_run_count,
              COUNT(*) FILTER (WHERE outcome = 'error')::INTEGER AS failed_sync_count
            FROM episode_sync_runs
            WHERE repo_id = :repo_id
              AND created_at >= :start_at
              AND created_at < :end_at;
            """
            ),
            {"repo_id": repo_id, "start_at": start_at, "end_at": end_at},
        )
        .mappings()
        .one()
    )
    return dict(row)
