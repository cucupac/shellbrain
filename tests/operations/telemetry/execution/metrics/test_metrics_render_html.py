"""Unit coverage for the static metrics dashboard renderer."""

from __future__ import annotations

from app.periphery.metrics.render_html import render_metrics_dashboard


def test_render_metrics_dashboard_should_embed_styles_and_limit_metric_cards() -> None:
    """The renderer should stay self-contained and bounded to four cards."""

    snapshot = {
        "repo_id": "github.com/example/repo",
        "generated_at": "2026-03-27T15:00:00+00:00",
        "window_days": 30,
        "current_window": {
            "start_at": "2026-02-26T00:00:00+00:00",
            "end_at": "2026-03-27T15:00:00+00:00",
        },
        "previous_window": {
            "start_at": "2026-01-28T09:00:00+00:00",
            "end_at": "2026-02-26T00:00:00+00:00",
        },
        "status": "healthy",
        "confidence": "medium",
        "headline": "Utility score trend is healthy for github.com/example/repo.",
        "alerts": [{"message": "Sync health is reducing confidence in the snapshot (2 failed sync runs out of 20)."}],
        "metrics": [_metric(name=f"Metric {index}") for index in range(1, 6)],
        "summary_md": "Metric 1 moved. Metric 2 matters. Metric 3 is next.",
    }

    html = render_metrics_dashboard(snapshot)

    assert "<style>" in html
    assert "<script" not in html
    assert "https://" not in html
    assert html.count('<article class="metric-card') == 4
    assert "Pipeline warning" in html
    assert "aria-label=\"Metric 1 sparkline\"" in html
    assert "Daily value" in html
    assert "7-day rolling average" in html
    assert "Zero baseline" in html


def _metric(*, name: str) -> dict[str, object]:
    """Return one minimal metric payload for renderer tests."""

    return {
        "name": name,
        "current": 0.6,
        "previous": 0.4,
        "delta": 0.2,
        "sample_count": 12,
        "confidence": "medium",
        "format": "percent",
        "daily_series": [
            {"date": "2026-03-26", "value": 0.5, "sample_count": 5, "rolling_value": 0.5},
            {"date": "2026-03-27", "value": 0.6, "sample_count": 7, "rolling_value": 0.55},
        ],
    }
