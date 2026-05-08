"""Browser helpers for opening generated metrics dashboards."""

from __future__ import annotations

from pathlib import Path
import webbrowser


def open_metrics_dashboard(path: Path) -> bool:
    """Open one generated dashboard in the default browser."""

    return bool(webbrowser.open(path.resolve().as_uri()))
