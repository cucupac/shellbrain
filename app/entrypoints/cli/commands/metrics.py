"""Metrics command implementation."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Callable


def run_metrics_command(args: argparse.Namespace, *, warn_or_fail_on_unsafe_app_role: Callable[[], None]) -> int:
    """Generate metrics snapshots and artifacts for one or many repos."""

    try:
        from app.startup.admin_db import get_optional_admin_db_dsn
        from app.startup.db import get_optional_db_dsn
        # architecture-compat: direct-periphery - metrics CLI composes DB and reporting adapters.
        from app.periphery.db.engine import get_engine
        from app.periphery.reporting.metrics.artifacts import write_metrics_artifacts, write_metrics_index_artifact
        # architecture-compat: direct-periphery - metrics CLI opens generated dashboard output.
        from app.periphery.reporting.metrics.browser import open_metrics_dashboard
        # architecture-compat: direct-periphery - metrics HTML rendering is an output adapter.
        from app.periphery.reporting.metrics.render_html import render_metrics_browser_dashboard, render_metrics_dashboard
        from app.startup.metrics import build_metrics_snapshot, list_metrics_repo_ids

        if bool(getattr(args, "repo_id", None) or getattr(args, "repo_root", None) or getattr(args, "no_sync", False)):
            raise ValueError("`shellbrain metrics` does not accept options. Run `shellbrain metrics`.")

        warn_or_fail_on_unsafe_app_role()
        dsn = get_optional_db_dsn() or get_optional_admin_db_dsn()
        if not dsn:
            raise RuntimeError("Shellbrain database is not configured. Run `shellbrain init` first.")
        engine = get_engine(dsn)

        target_repo_ids = list_metrics_repo_ids(engine=engine)
        if not target_repo_ids:
            print("No tracked repos found in metrics telemetry yet.")
            return 0

        entries: list[dict[str, Any]] = []
        window_days = 30
        for repo_id in target_repo_ids:
            snapshot = build_metrics_snapshot(engine=engine, repo_id=repo_id, days=window_days)
            html = render_metrics_dashboard(snapshot)
            paths = write_metrics_artifacts(repo_id=repo_id, snapshot=snapshot, html=html)
            entries.append({"snapshot": snapshot, "paths": paths})

        overview_path = write_metrics_index_artifact(
            html=render_metrics_browser_dashboard([entry["snapshot"] for entry in entries])
        )
        opened_dashboard = bool(open_metrics_dashboard(Path(overview_path)))
        print(f"Generated Shellbrain metrics for {len(entries)} repos")
        print(f"Window: last {window_days} days")
        print("Artifacts: updated in place")
        if opened_dashboard:
            print("Browser: opened dashboard; use left/right arrow keys in the browser to switch repos")
        else:
            print(f"Browser: could not open automatically; open {overview_path}")
        return 0
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
