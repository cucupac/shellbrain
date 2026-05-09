"""Human-facing metrics dashboard output."""

from __future__ import annotations

from app.core.use_cases.metrics.generate_dashboard import MetricsDashboardResult


def render_metrics_dashboard_lines(result: MetricsDashboardResult) -> list[str]:
    """Render dashboard generation results as CLI status lines."""

    if not result.entries:
        return ["No tracked repos found in metrics telemetry yet."]
    lines = [
        f"Generated Shellbrain metrics for {len(result.entries)} repos",
        f"Window: last {result.window_days} days",
        "Artifacts: updated in place",
    ]
    if result.opened_dashboard:
        lines.append(
            "Browser: opened dashboard; use left/right arrow keys in the browser to switch repos"
        )
    else:
        lines.append(
            f"Browser: could not open automatically; open {result.overview_path}"
        )
    return lines
