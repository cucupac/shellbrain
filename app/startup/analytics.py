"""Composition wrapper for admin analytics reporting."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.engine import Engine

from app.core.use_cases.admin.generate_analytics_report import (
    build_analytics_report as build_analytics_report_from_rows,
)
from app.infrastructure.db.queries.analytics import (
    fetch_events_for_threads,
    fetch_operation_invocations,
    fetch_pending_utility_threads,
    fetch_read_summaries,
    fetch_sync_runs,
    fetch_utility_vote_writes_for_threads,
    fetch_write_summaries,
)


def build_analytics_report(*, engine: Engine, days: int) -> dict:
    """Fetch analytics rows through SQL adapters and build the core report."""

    if days <= 0:
        raise ValueError("--days must be greater than 0")
    end_at = datetime.now(timezone.utc)
    start_at = end_at - timedelta(days=days)
    with engine.connect() as conn:
        operation_rows = fetch_operation_invocations(conn=conn, start_at=start_at)
        read_rows = fetch_read_summaries(conn=conn, start_at=start_at)
        write_rows = fetch_write_summaries(conn=conn, start_at=start_at)
        sync_rows = fetch_sync_runs(conn=conn, start_at=start_at)
        pending_threads = fetch_pending_utility_threads(conn=conn, start_at=start_at)
        thread_keys = [
            (str(row["repo_id"]), str(row["selected_thread_id"]))
            for row in pending_threads
            if isinstance(row.get("selected_thread_id"), str)
        ]
        utility_vote_rows = fetch_utility_vote_writes_for_threads(
            conn=conn, thread_keys=thread_keys
        )
        event_thread_keys = [
            (str(row["repo_id"]), str(row["selected_thread_id"]))
            for row in write_rows
            if isinstance(row.get("selected_thread_id"), str)
        ]
        event_rows = fetch_events_for_threads(conn=conn, thread_keys=event_thread_keys)

    return build_analytics_report_from_rows(
        days=days,
        end_at=end_at,
        operation_rows=operation_rows,
        read_rows=read_rows,
        write_rows=write_rows,
        sync_rows=sync_rows,
        pending_threads=pending_threads,
        utility_vote_rows=utility_vote_rows,
        event_rows=event_rows,
    )
