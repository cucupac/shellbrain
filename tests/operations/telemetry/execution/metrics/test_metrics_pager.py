"""Coverage for the terminal metrics pager renderer."""

from __future__ import annotations

import io
from pathlib import Path

from app.infrastructure.reporting.metrics.pager import present_metrics_repo_pager


def test_present_metrics_repo_pager_should_render_all_entries_for_non_interactive_streams(
    tmp_path: Path,
) -> None:
    """Non-interactive streams should receive one plain-text block per repo entry."""

    output = io.StringIO()
    present_metrics_repo_pager(
        entries=[
            {
                "snapshot": _snapshot(repo_id="github.com/example/one"),
                "paths": _paths(tmp_path, "one"),
            },
            {
                "snapshot": _snapshot(repo_id="github.com/example/two"),
                "paths": _paths(tmp_path, "two"),
            },
        ],
        stdin=io.StringIO(),
        stdout=output,
    )

    text = output.getvalue()
    assert "Repo: github.com/example/one" in text
    assert "Repo: github.com/example/two" in text
    assert "Utility score trend: now 0.600 | prev 0.400 | delta +0.200 | n=12" in text
    assert "Dashboard: " in text


def test_present_metrics_repo_pager_should_print_empty_message_when_no_entries() -> (
    None
):
    """Empty snapshots should produce one short user-facing message."""

    output = io.StringIO()
    present_metrics_repo_pager(entries=[], stdin=io.StringIO(), stdout=output)

    assert output.getvalue() == "No metrics snapshots are available.\n"


def _snapshot(*, repo_id: str) -> dict[str, object]:
    """Return one stable snapshot payload for pager rendering tests."""

    return {
        "repo_id": repo_id,
        "generated_at": "2026-03-27T15:00:00+00:00",
        "window_days": 30,
        "status": "healthy",
        "confidence": "medium",
        "metrics": [
            _metric(
                name="Utility score trend",
                current=0.6,
                previous=0.4,
                delta=0.2,
                sample_count=12,
                format_name="score",
            ),
            _metric(
                name="Utility follow-through",
                current=0.75,
                previous=0.5,
                delta=0.25,
                sample_count=8,
                format_name="percent",
            ),
        ],
    }


def _paths(root: Path, slug: str) -> dict[str, Path]:
    """Return one stable path map for pager tests."""

    base = root / slug
    return {
        "json_path": base / "latest.json",
        "md_path": base / "latest.md",
        "html_path": base / "dashboard.html",
    }


def _metric(
    *,
    name: str,
    current: float,
    previous: float,
    delta: float,
    sample_count: int,
    format_name: str,
) -> dict[str, object]:
    """Return one metric payload fragment."""

    return {
        "name": name,
        "current": current,
        "previous": previous,
        "delta": delta,
        "sample_count": sample_count,
        "confidence": "medium",
        "format": format_name,
        "daily_series": [],
    }
