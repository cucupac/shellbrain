"""Composition wrapper for repo-scoped metrics snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.engine import Engine

from app.core.use_cases.metrics import build_snapshot as core_metrics
from app.core.use_cases.metrics.generate_dashboard import (
    MetricsDashboardResult,
    generate_metrics_dashboard,
)
from app.infrastructure.db.runtime import engine as db_engine
from app.infrastructure.db.runtime.queries.metrics_adapter import SqlMetricsQueries
from app.infrastructure.reporting.metrics import artifacts as metric_artifacts
from app.infrastructure.reporting.metrics import browser as metric_browser
from app.infrastructure.reporting.metrics import render_html
from app.startup import admin_db, db as startup_db


_REAL_DATETIME = datetime


def list_metrics_repo_ids(*, engine: Engine) -> list[str]:
    """Return repo ids using SQL query adapters."""

    with engine.connect() as conn:
        return core_metrics.list_metrics_repo_ids(queries=SqlMetricsQueries(conn))


def build_metrics_snapshot(*, engine: Engine, repo_id: str, days: int) -> dict:
    """Return a metrics snapshot using SQL query adapters."""

    end_at = _REAL_DATETIME.now(timezone.utc)
    with engine.connect() as conn:
        return core_metrics.build_metrics_snapshot(
            queries=SqlMetricsQueries(conn),
            repo_id=repo_id,
            days=days,
            end_at=end_at,
        )


def run_metrics_dashboard(
    *, warn_or_fail_on_unsafe_app_role: Callable[[], None]
) -> MetricsDashboardResult:
    """Wire concrete metrics adapters and generate dashboard artifacts."""

    warn_or_fail_on_unsafe_app_role()
    dsn = startup_db.get_optional_db_dsn() or admin_db.get_optional_admin_db_dsn()
    if not dsn:
        raise RuntimeError(
            "Shellbrain database is not configured. Run `shellbrain init` first."
        )
    engine = db_engine.get_engine(dsn)

    with engine.connect() as conn:
        return generate_metrics_dashboard(
            queries=SqlMetricsQueries(conn),
            renderer=render_html,
            artifact_writer=metric_artifacts,
            browser=metric_browser,
            end_at=_REAL_DATETIME.now(timezone.utc),
        )
