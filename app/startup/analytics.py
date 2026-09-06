"""Fetch the measurements used by the admin analytics report."""

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.use_cases.admin.generate_analytics_report import (
    build_analytics_report as summarize,
)
from app.infrastructure.db.runtime.queries.analytics import (
    fetch_operation_invocations,
    fetch_read_summaries,
    fetch_sync_runs,
)


def build_analytics_report(*, engine: Any, days: int) -> dict:
    if days <= 0:
        raise ValueError("--days must be greater than 0")
    end_at = datetime.now(timezone.utc)
    start_at = end_at - timedelta(days=days)
    with engine.connect() as conn:
        return summarize(
            days=days,
            end_at=end_at,
            operation_rows=fetch_operation_invocations(conn=conn, start_at=start_at),
            read_rows=fetch_read_summaries(conn=conn, start_at=start_at),
            sync_rows=fetch_sync_runs(conn=conn, start_at=start_at),
        )
