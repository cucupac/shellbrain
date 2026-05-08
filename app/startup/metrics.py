"""Composition wrapper for repo-scoped metrics snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy.engine import Connection, Engine

from app.core.use_cases.metrics import build_snapshot as core_metrics
from app.infrastructure.db import engine as db_engine
from app.infrastructure.db.queries import metrics as metric_queries
from app.infrastructure.reporting.metrics import artifacts as metric_artifacts
from app.infrastructure.reporting.metrics import browser as metric_browser
from app.infrastructure.reporting.metrics import render_html
from app.startup import admin_db, db as startup_db


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


def run_metrics_dashboard(*, warn_or_fail_on_unsafe_app_role: Callable[[], None]) -> list[str]:
    """Generate metrics snapshots, artifacts, and dashboard output."""

    warn_or_fail_on_unsafe_app_role()
    dsn = startup_db.get_optional_db_dsn() or admin_db.get_optional_admin_db_dsn()
    if not dsn:
        raise RuntimeError("Shellbrain database is not configured. Run `shellbrain init` first.")
    engine = db_engine.get_engine(dsn)

    target_repo_ids = list_metrics_repo_ids(engine=engine)
    if not target_repo_ids:
        return ["No tracked repos found in metrics telemetry yet."]

    entries: list[dict[str, object]] = []
    window_days = 30
    for repo_id in target_repo_ids:
        snapshot = build_metrics_snapshot(engine=engine, repo_id=repo_id, days=window_days)
        html = render_html.render_metrics_dashboard(snapshot)
        paths = metric_artifacts.write_metrics_artifacts(repo_id=repo_id, snapshot=snapshot, html=html)
        entries.append({"snapshot": snapshot, "paths": paths})

    overview_path = metric_artifacts.write_metrics_index_artifact(
        html=render_html.render_metrics_browser_dashboard([entry["snapshot"] for entry in entries])
    )
    opened_dashboard = bool(metric_browser.open_metrics_dashboard(Path(overview_path)))
    lines = [
        f"Generated Shellbrain metrics for {len(entries)} repos",
        f"Window: last {window_days} days",
        "Artifacts: updated in place",
    ]
    if opened_dashboard:
        lines.append("Browser: opened dashboard; use left/right arrow keys in the browser to switch repos")
    else:
        lines.append(f"Browser: could not open automatically; open {overview_path}")
    return lines
