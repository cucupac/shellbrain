"""Ports for metrics dashboard generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class MetricsHtmlRenderer(Protocol):
    """Render metrics snapshots to HTML."""

    def render_metrics_dashboard(self, snapshot: dict[str, Any]) -> str: ...

    def render_metrics_browser_dashboard(self, snapshots: list[dict[str, Any]]) -> str: ...


class MetricsArtifactWriter(Protocol):
    """Persist rendered metrics artifacts."""

    def write_metrics_artifacts(self, *, repo_id: str, snapshot: dict[str, Any], html: str) -> dict[str, Path | str]: ...

    def write_metrics_index_artifact(self, *, html: str) -> Path | str: ...


class MetricsDashboardBrowser(Protocol):
    """Open a generated metrics dashboard when possible."""

    def open_metrics_dashboard(self, path: Path) -> bool: ...
