"""Read-only query helpers for the admin analytics report."""

from __future__ import annotations

from collections.abc import Sequence
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
            ORDER BY oi.created_at ASC, oi.id ASC;
            """
        ),
        {"start_at": start_at},
    ).mappings()
    return [dict(row) for row in rows]


def fetch_write_summaries(
    *, conn: Connection, start_at: datetime
) -> list[dict[str, object]]:
    """Return write summaries inside the reporting window."""

    rows = conn.execute(
        text(
            """
            SELECT
              oi.id AS invocation_id,
              oi.repo_id,
              oi.selected_thread_id,
              oi.command,
              oi.created_at,
              wis.update_type
            FROM write_invocation_summaries wis
            JOIN operation_invocations oi ON oi.id = wis.invocation_id
            WHERE oi.created_at >= :start_at
            ORDER BY oi.created_at ASC, oi.id ASC;
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


def fetch_pending_utility_threads(
    *, conn: Connection, start_at: datetime
) -> list[dict[str, object]]:
    """Return threads that emitted pending utility-vote guidance in the reporting window."""

    rows = conn.execute(
        text(
            """
            SELECT
              repo_id,
              selected_thread_id,
              MIN(created_at) AS first_guidance_at,
              COUNT(*)::INTEGER AS reminder_count
            FROM operation_invocations
            WHERE created_at >= :start_at
              AND selected_thread_id IS NOT NULL
              AND guidance_codes @> '["pending_utility_votes"]'::jsonb
            GROUP BY repo_id, selected_thread_id
            ORDER BY MIN(created_at) ASC;
            """
        ),
        {"start_at": start_at},
    ).mappings()
    return [dict(row) for row in rows]


def fetch_utility_vote_writes_for_threads(
    *,
    conn: Connection,
    thread_keys: Sequence[tuple[str, str]],
) -> list[dict[str, object]]:
    """Return utility-vote writes for the selected repo/thread pairs."""

    if not thread_keys:
        return []
    repo_ids = [repo_id for repo_id, _thread_id in thread_keys]
    thread_ids = [thread_id for _repo_id, thread_id in thread_keys]
    allowed_pairs = set(thread_keys)
    rows = conn.execute(
        text(
            """
            SELECT
              oi.repo_id,
              oi.selected_thread_id,
              oi.created_at,
              wis.update_type,
              oi.id AS invocation_id
            FROM write_invocation_summaries wis
            JOIN operation_invocations oi ON oi.id = wis.invocation_id
            WHERE oi.repo_id = ANY(:repo_ids)
              AND oi.selected_thread_id = ANY(:thread_ids)
              AND wis.update_type IN ('utility_vote', 'utility_vote_batch')
            ORDER BY oi.created_at ASC, oi.id ASC;
            """
        ),
        {"repo_ids": repo_ids, "thread_ids": thread_ids},
    ).mappings()
    return [
        dict(row)
        for row in rows
        if (str(row["repo_id"]), str(row["selected_thread_id"])) in allowed_pairs
    ]


def fetch_events_for_threads(
    *,
    conn: Connection,
    thread_keys: Sequence[tuple[str, str]],
) -> list[dict[str, object]]:
    """Return all events invocations for the selected repo/thread pairs."""

    if not thread_keys:
        return []
    repo_ids = [repo_id for repo_id, _thread_id in thread_keys]
    thread_ids = [thread_id for _repo_id, thread_id in thread_keys]
    allowed_pairs = set(thread_keys)
    rows = conn.execute(
        text(
            """
            SELECT
              repo_id,
              selected_thread_id,
              created_at,
              id AS invocation_id
            FROM operation_invocations
            WHERE command = 'events'
              AND repo_id = ANY(:repo_ids)
              AND selected_thread_id = ANY(:thread_ids)
            ORDER BY created_at ASC, id ASC;
            """
        ),
        {"repo_ids": repo_ids, "thread_ids": thread_ids},
    ).mappings()
    return [
        dict(row)
        for row in rows
        if (str(row["repo_id"]), str(row["selected_thread_id"])) in allowed_pairs
    ]
