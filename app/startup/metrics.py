"""Composition wrapper for repo-scoped metrics snapshots."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.engine import Connection, Engine

from app.core.use_cases.metrics import build_snapshot as core_metrics
from app.periphery.db.queries import metrics as metric_queries


_REAL_DATETIME = datetime


class _SqlMetricsQueries:
    """SQL-backed metrics query adapter."""

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def fetch_metrics_repo_ids(self) -> list[str]:
        return metric_queries.fetch_metrics_repo_ids(conn=self._conn)

    def fetch_daily_utility_rows(self, *, repo_id: str, start_at: datetime, end_at: datetime) -> list[dict[str, object]]:
        return metric_queries.fetch_daily_utility_rows(conn=self._conn, repo_id=repo_id, start_at=start_at, end_at=end_at)

    def fetch_daily_followthrough_rows(self, *, repo_id: str, start_at: datetime, end_at: datetime) -> list[dict[str, object]]:
        return metric_queries.fetch_daily_followthrough_rows(conn=self._conn, repo_id=repo_id, start_at=start_at, end_at=end_at)

    def fetch_daily_zero_result_rows(self, *, repo_id: str, start_at: datetime, end_at: datetime) -> list[dict[str, object]]:
        return metric_queries.fetch_daily_zero_result_rows(conn=self._conn, repo_id=repo_id, start_at=start_at, end_at=end_at)

    def fetch_daily_events_before_write_rows(self, *, repo_id: str, start_at: datetime, end_at: datetime) -> list[dict[str, object]]:
        return metric_queries.fetch_daily_events_before_write_rows(conn=self._conn, repo_id=repo_id, start_at=start_at, end_at=end_at)

    def fetch_sync_health_summary(self, *, repo_id: str, start_at: datetime, end_at: datetime) -> dict[str, object]:
        return metric_queries.fetch_sync_health_summary(conn=self._conn, repo_id=repo_id, start_at=start_at, end_at=end_at)


def list_metrics_repo_ids(*, engine: Engine) -> list[str]:
    """Return repo ids using SQL query adapters."""

    with engine.connect() as conn:
        return core_metrics.list_metrics_repo_ids(queries=_SqlMetricsQueries(conn))


def build_metrics_snapshot(*, engine: Engine, repo_id: str, days: int) -> dict:
    """Return a metrics snapshot using SQL query adapters."""

    end_at = _REAL_DATETIME.now(timezone.utc)
    with engine.connect() as conn:
        return core_metrics.build_metrics_snapshot(
            queries=_SqlMetricsQueries(conn),
            repo_id=repo_id,
            days=days,
            end_at=end_at,
        )
