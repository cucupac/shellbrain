"""SQL-backed metrics query adapter."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.engine import Connection

from app.infrastructure.db.runtime.queries import metrics as metric_queries


class SqlMetricsQueries:
    """SQL-backed implementation of the core metrics query port."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def fetch_metrics_repo_ids(self) -> list[str]:
        return metric_queries.fetch_metrics_repo_ids(conn=self._conn)

    def fetch_daily_utility_rows(
        self, *, repo_id: str, start_at: datetime, end_at: datetime
    ) -> list[dict[str, object]]:
        return metric_queries.fetch_daily_utility_rows(
            conn=self._conn, repo_id=repo_id, start_at=start_at, end_at=end_at
        )

    def fetch_daily_followthrough_rows(
        self, *, repo_id: str, start_at: datetime, end_at: datetime
    ) -> list[dict[str, object]]:
        return metric_queries.fetch_daily_followthrough_rows(
            conn=self._conn, repo_id=repo_id, start_at=start_at, end_at=end_at
        )

    def fetch_daily_zero_result_rows(
        self, *, repo_id: str, start_at: datetime, end_at: datetime
    ) -> list[dict[str, object]]:
        return metric_queries.fetch_daily_zero_result_rows(
            conn=self._conn, repo_id=repo_id, start_at=start_at, end_at=end_at
        )

    def fetch_daily_events_before_write_rows(
        self, *, repo_id: str, start_at: datetime, end_at: datetime
    ) -> list[dict[str, object]]:
        return metric_queries.fetch_daily_events_before_write_rows(
            conn=self._conn, repo_id=repo_id, start_at=start_at, end_at=end_at
        )

    def fetch_sync_health_summary(
        self, *, repo_id: str, start_at: datetime, end_at: datetime
    ) -> dict[str, object]:
        return metric_queries.fetch_sync_health_summary(
            conn=self._conn, repo_id=repo_id, start_at=start_at, end_at=end_at
        )
