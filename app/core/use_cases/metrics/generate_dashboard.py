"""Generate metrics dashboard artifacts through explicit ports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.ports.reporting.metrics import (
    MetricsArtifactWriter,
    MetricsDashboardBrowser,
    MetricsHtmlRenderer,
)
from app.core.use_cases.metrics.build_snapshot import (
    MetricsQueryPort,
    build_metrics_snapshot,
    list_metrics_repo_ids,
)


@dataclass(frozen=True)
class MetricsDashboardEntry:
    """One generated repo dashboard entry."""

    snapshot: dict[str, Any]
    paths: dict[str, Path | str]


@dataclass(frozen=True)
class MetricsDashboardResult:
    """Result of one dashboard generation workflow."""

    entries: list[MetricsDashboardEntry]
    overview_path: Path | str | None
    opened_dashboard: bool
    window_days: int


def generate_metrics_dashboard(
    *,
    queries: MetricsQueryPort,
    renderer: MetricsHtmlRenderer,
    artifact_writer: MetricsArtifactWriter,
    browser: MetricsDashboardBrowser,
    end_at: datetime,
    window_days: int = 30,
) -> MetricsDashboardResult:
    """Generate metrics snapshots, rendered artifacts, and optional browser opening."""

    target_repo_ids = list_metrics_repo_ids(queries=queries)
    if not target_repo_ids:
        return MetricsDashboardResult(
            entries=[],
            overview_path=None,
            opened_dashboard=False,
            window_days=window_days,
        )

    entries: list[MetricsDashboardEntry] = []
    for repo_id in target_repo_ids:
        snapshot = build_metrics_snapshot(
            queries=queries, repo_id=repo_id, days=window_days, end_at=end_at
        )
        html = renderer.render_metrics_dashboard(snapshot)
        paths = artifact_writer.write_metrics_artifacts(
            repo_id=repo_id, snapshot=snapshot, html=html
        )
        entries.append(MetricsDashboardEntry(snapshot=snapshot, paths=paths))

    overview_path = artifact_writer.write_metrics_index_artifact(
        html=renderer.render_metrics_browser_dashboard(
            [entry.snapshot for entry in entries]
        )
    )
    opened_dashboard = bool(browser.open_metrics_dashboard(Path(overview_path)))
    return MetricsDashboardResult(
        entries=entries,
        overview_path=overview_path,
        opened_dashboard=opened_dashboard,
        window_days=window_days,
    )
