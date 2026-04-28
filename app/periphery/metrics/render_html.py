"""Render one self-contained HTML dashboard for Shellbrain metrics."""

from __future__ import annotations

from html import escape
from typing import Any, Sequence


_PAGE_CSS = """
:root {
  --bg: #0f1117;
  --surface: #1a1d2e;
  --surface2: #22263a;
  --surface3: #2a2f47;
  --border: #2e3354;
  --accent: #6c8fff;
  --green: #3ecf8e;
  --green-soft: rgba(62,207,142,0.12);
  --red: #f87171;
  --red-soft: rgba(248,113,113,0.12);
  --yellow: #fbbf24;
  --yellow-soft: rgba(251,191,36,0.12);
  --blue-soft: rgba(108,143,255,0.12);
  --muted: #8892b0;
  --text: #e2e8f0;
  --text-dim: #a0aec0;
  --shadow: 0 8px 32px rgba(0,0,0,0.3);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html, body {
  min-height: 100%;
  background: var(--bg);
  color: var(--text);
}

body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  font-size: 14px;
  line-height: 1.6;
}

.shell {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 28px 64px;
}

.status-strip,
.alert-strip {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  border-radius: 10px;
  padding: 14px 18px;
  border: 1px solid var(--border);
  background: var(--surface2);
}

.status-strip { margin-bottom: 16px; }
.alert-strip { margin-bottom: 16px; }

.masthead {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-end;
  padding: 18px 0 22px;
  border-bottom: 1px solid var(--border);
}

.eyebrow {
  margin: 0 0 6px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 11px;
  color: var(--accent);
  font-weight: 700;
}

.masthead h1 {
  font-size: 22px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--text);
}

.masthead-meta {
  max-width: 480px;
  padding: 14px 18px;
  border-radius: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--muted);
  font-size: 12px;
}

.dashboard {
  display: grid;
  gap: 20px;
  padding-top: 24px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.metric-card {
  border-radius: 10px;
  padding: 18px;
  border: 1px solid var(--border);
  background: var(--surface2);
  box-shadow: var(--shadow);
}

.metric-card .label {
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-size: 11px;
  font-weight: 600;
}

.metric-card .value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.metric-card .meta {
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
}

.sparkline-frame {
  margin-top: 14px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: linear-gradient(180deg, var(--surface2), var(--surface));
  padding: 10px 12px;
}

.sparkline-frame svg {
  display: block;
  width: 100%;
  height: 84px;
}

.chart-legend {
  margin-top: 8px;
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: 11px;
}

.legend-item {
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.legend-swatch {
  width: 14px;
  height: 2px;
  border-radius: 999px;
  background: var(--text-dim);
}

.legend-swatch.rolling {
  background: var(--accent);
}

.legend-swatch.baseline {
  background: rgba(46,51,84,0.8);
}

.pill-row {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.pill {
  border-radius: 999px;
  padding: 5px 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-dim);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 700;
}

.pill.neutral { background: var(--surface); }
.tone-positive { background: var(--green-soft); border-color: rgba(62,207,142,0.2); }
.tone-warning  { background: var(--yellow-soft); border-color: rgba(251,191,36,0.2); }
.tone-danger   { background: var(--red-soft); border-color: rgba(248,113,113,0.2); }
.tone-info     { background: var(--blue-soft); border-color: rgba(108,143,255,0.2); }

.subtle {
  color: var(--muted);
  font-size: 12px;
}

@media (max-width: 900px) {
  .metric-grid { grid-template-columns: 1fr; }
  .masthead, .status-strip, .alert-strip { flex-direction: column; align-items: flex-start; }
}
"""


_BROWSER_CSS = """
.browser-shell {
  max-width: 1440px;
  margin: 0 auto;
  padding: 24px 28px 64px;
}

.browser-masthead {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-end;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border);
}

.browser-masthead h1 {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.browser-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.browser-keyhint {
  margin-top: 12px;
  color: var(--muted);
  font-size: 12px;
}

.repo-tab-row {
  margin-top: 18px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.repo-tab {
  appearance: none;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text-dim);
  padding: 8px 12px;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  transition: background 140ms ease, color 140ms ease, border-color 140ms ease;
}

.repo-tab.is-active {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.repo-browser {
  margin-top: 20px;
}

.repo-panel[hidden] {
  display: none !important;
}
"""


_BROWSER_SCRIPT = """
<script>
(() => {
  const panels = Array.from(document.querySelectorAll(".repo-panel"));
  const tabs = Array.from(document.querySelectorAll(".repo-tab"));
  const position = document.getElementById("repo-position");
  const status = document.getElementById("repo-status");
  if (!panels.length) {
    return;
  }

  let index = 0;

  const show = (nextIndex) => {
    index = (nextIndex + panels.length) % panels.length;
    panels.forEach((panel, panelIndex) => {
      const active = panelIndex === index;
      panel.hidden = !active;
      panel.setAttribute("aria-hidden", active ? "false" : "true");
    });
    tabs.forEach((tab, tabIndex) => {
      const active = tabIndex === index;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-pressed", active ? "true" : "false");
      tab.tabIndex = active ? 0 : -1;
    });

    const activePanel = panels[index];
    const repoId = activePanel.dataset.repoId || "";
    const tone = activePanel.dataset.tone || "neutral";
    const statusText = activePanel.dataset.status || "unknown";

    if (position) {
      position.textContent = `${index + 1} / ${panels.length}`;
    }
    if (status) {
      status.className = `pill ${tone}`;
      status.textContent = statusText.replaceAll("_", " ");
      status.setAttribute("aria-label", `${repoId} status ${statusText}`);
    }
    document.title = `Shellbrain Metrics - ${repoId}`;
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, "", `#repo-${index + 1}`);
    }
  };

  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) {
      return;
    }

    const target = event.target;
    const tagName = target && target.tagName ? target.tagName.toLowerCase() : "";
    if (tagName === "input" || tagName === "textarea" || tagName === "select") {
      return;
    }
    if (target && target.isContentEditable) {
      return;
    }

    if (event.key === "ArrowRight") {
      event.preventDefault();
      show(index + 1);
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      show(index - 1);
    }
  });

  tabs.forEach((tab, tabIndex) => {
    tab.addEventListener("click", () => show(tabIndex));
  });

  const hashMatch = window.location.hash.match(/^#repo-(\\d+)$/);
  if (hashMatch) {
    const parsed = Number(hashMatch[1]);
    if (!Number.isNaN(parsed) && parsed >= 1 && parsed <= panels.length) {
      index = parsed - 1;
    }
  }

  show(index);
})();
</script>
"""


def render_metrics_dashboard(snapshot: dict[str, Any]) -> str:
    """Render one self-contained HTML dashboard from a metrics snapshot."""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Shellbrain Metrics</title>
  <link rel="icon" href="data:,">
  <style>{_PAGE_CSS}</style>
</head>
<body>
  <div class="shell">
    {_render_snapshot_content(snapshot)}
  </div>
</body>
</html>
"""


def render_metrics_browser_dashboard(snapshots: Sequence[dict[str, Any]]) -> str:
    """Render one browser dashboard that switches repos with in-page arrow-key navigation."""

    normalized = [snapshot for snapshot in snapshots if isinstance(snapshot, dict)]
    if not normalized:
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Shellbrain Metrics</title>
  <link rel="icon" href="data:,">
  <style>body{font-family:system-ui,sans-serif;padding:24px}</style>
</head>
<body><p>No metrics snapshots are available.</p></body>
</html>
"""

    first_snapshot = normalized[0]
    tabs = "".join(
        f"<button type=\"button\" class=\"repo-tab{' is-active' if index == 0 else ''}\" aria-pressed=\"{'true' if index == 0 else 'false'}\">{escape(str(snapshot['repo_id']))}</button>"
        for index, snapshot in enumerate(normalized)
    )
    panels = "".join(
        _render_browser_panel(snapshot=snapshot, index=index)
        for index, snapshot in enumerate(normalized)
    )
    first_tone = _tone_for_status(str(first_snapshot["status"]))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Shellbrain Metrics - {escape(str(first_snapshot["repo_id"]))}</title>
  <link rel="icon" href="data:,">
  <style>{_PAGE_CSS}{_BROWSER_CSS}</style>
</head>
<body>
  <div class="browser-shell">
    <header class="browser-masthead">
      <div>
        <p class="eyebrow">Shellbrain Metrics</p>
        <h1>All Repos</h1>
        <div class="subtle">Opened automatically. Use the left and right arrow keys in this page to switch repos.</div>
      </div>
      <div class="browser-meta">
        <span id="repo-position" class="pill neutral">1 / {len(normalized)}</span>
        <span id="repo-status" class="pill {first_tone}">{escape(str(first_snapshot["status"]).replace("_", " "))}</span>
      </div>
    </header>
    <div class="browser-keyhint">Left/Right arrow keys switch repos in this page. No terminal input is required.</div>
    <nav class="repo-tab-row" aria-label="Tracked repos">
      {tabs}
    </nav>
    <main class="repo-browser">
      {panels}
    </main>
  </div>
  {_BROWSER_SCRIPT}
</body>
</html>
"""


def _render_browser_panel(*, snapshot: dict[str, Any], index: int) -> str:
    """Render one repo panel for the multi-repo browser dashboard."""

    tone = _tone_for_status(str(snapshot["status"]))
    hidden_attr = "" if index == 0 else " hidden"
    return f"""
    <section class="repo-panel" data-repo-id="{escape(str(snapshot["repo_id"]))}" data-status="{escape(str(snapshot["status"]))}" data-tone="{tone}" aria-hidden="{'false' if index == 0 else 'true'}"{hidden_attr}>
      {_render_snapshot_content(snapshot)}
    </section>
    """


def _render_snapshot_content(snapshot: dict[str, Any]) -> str:
    """Render the shared snapshot content used by single-repo and multi-repo dashboards."""

    status_tone = _tone_for_status(str(snapshot["status"]))
    alert_html = ""
    if snapshot["alerts"]:
        alert = snapshot["alerts"][0]
        alert_html = f"""
        <section class="alert-strip tone-warning">
          <div><strong>Pipeline warning</strong><div class="subtle">{escape(str(alert["message"]))}</div></div>
          <div class="pill-row"><span class="pill tone-warning">Sync Confidence Modifier</span></div>
        </section>
        """

    metric_cards = "".join(_render_metric_card(metric) for metric in list(snapshot["metrics"])[:4])
    generated_at = escape(str(snapshot["generated_at"]).replace("T", " ").replace("+00:00", " UTC"))
    current_window = snapshot["current_window"]

    return f"""
    <section class="status-strip {status_tone}">
      <div>
        <p class="eyebrow">Shellbrain Metrics</p>
        <div><strong>{escape(_status_title(str(snapshot["status"])))}</strong></div>
        <div class="subtle">{escape(str(snapshot["headline"]))}</div>
      </div>
      <div class="pill-row">
        <span class="pill {status_tone}">{escape(str(snapshot["status"]).replace("_", " "))}</span>
        <span class="pill neutral">{escape(str(snapshot["confidence"]))} confidence</span>
      </div>
    </section>

    <header class="masthead">
      <div>
        <p class="eyebrow">Repo Health</p>
        <h1>{escape(str(snapshot["repo_id"]))}</h1>
      </div>
      <div class="masthead-meta">
        <div><strong>Window:</strong> {escape(str(snapshot["window_days"]))} trailing days</div>
        <div><strong>Current window:</strong> {escape(str(current_window["start_at"]))} to {escape(str(current_window["end_at"]))}</div>
        <div><strong>Generated:</strong> {generated_at}</div>
      </div>
    </header>

    <main class="dashboard">
      {alert_html}
      <section class="metric-grid">
        {metric_cards}
      </section>
    </main>
    """


def _render_metric_card(metric: dict[str, Any]) -> str:
    """Render one metric card with a compact sparkline."""

    tone = _tone_for_metric(metric)
    chart = _render_sparkline(metric=metric)
    legend = _render_chart_legend(metric=metric)
    sample_label = _sample_label(metric)
    delta_text = _format_delta(metric)
    return f"""
    <article class="metric-card {tone}">
      <div class="label">{escape(str(metric["name"]))}</div>
      <div class="value">{escape(_format_value(metric["current"], str(metric["format"])))}</div>
      <div class="meta">{escape(f"Prev {_format_value(metric['previous'], str(metric['format']))} | {delta_text} | {sample_label} | {metric['confidence']} confidence")}</div>
      <div class="sparkline-frame">{chart}{legend}</div>
    </article>
    """


def _render_sparkline(*, metric: dict[str, Any]) -> str:
    """Render one inline SVG sparkline for a metric."""

    series = list(metric["daily_series"])
    if not series:
        return "<div class=\"subtle\">No data available.</div>"

    width = 420
    height = 84
    padding_x = 10
    padding_y = 12
    chart_width = width - padding_x * 2
    chart_height = height - padding_y * 2

    format_name = str(metric["format"])
    if format_name == "score":
        min_value = -1.0
        max_value = 1.0
    else:
        min_value = 0.0
        max_value = 1.0

    value_points = _series_points(series=series, key="value", width=chart_width, height=chart_height, min_value=min_value, max_value=max_value, padding_x=padding_x, padding_y=padding_y)
    rolling_points = _series_points(series=series, key="rolling_value", width=chart_width, height=chart_height, min_value=min_value, max_value=max_value, padding_x=padding_x, padding_y=padding_y)

    baseline_y = _scale_y(
        value=0.0,
        min_value=min_value,
        max_value=max_value,
        height=chart_height,
        padding_y=padding_y,
    )
    baseline = f"<line x1=\"{padding_x}\" y1=\"{baseline_y:.2f}\" x2=\"{padding_x + chart_width}\" y2=\"{baseline_y:.2f}\" stroke=\"rgba(46,51,84,0.8)\" stroke-width=\"1\" />"

    value_path = _path_from_points(value_points)
    rolling_path = _path_from_points(rolling_points)

    value_svg = ""
    if value_path:
        value_svg = f"<path d=\"{value_path}\" fill=\"none\" stroke=\"rgba(160,174,192,0.95)\" stroke-width=\"2\" />"
    rolling_svg = ""
    if rolling_path:
        rolling_svg = f"<path d=\"{rolling_path}\" fill=\"none\" stroke=\"rgba(108,143,255,0.95)\" stroke-width=\"2.5\" />"

    points_svg = "".join(
        f"<circle cx=\"{x:.2f}\" cy=\"{y:.2f}\" r=\"2.5\" fill=\"rgba(226,232,240,0.9)\" />"
        for x, y in value_points
    )

    return f"""
    <svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(str(metric['name']))} sparkline">
      {baseline}
      {value_svg}
      {rolling_svg}
      {points_svg}
    </svg>
    """


def _render_chart_legend(*, metric: dict[str, Any]) -> str:
    """Render one compact legend that explains the sparkline encoding."""

    has_rolling = any(row.get("rolling_value") is not None for row in metric["daily_series"])
    items = [
        "<span class=\"legend-item\"><span class=\"legend-swatch\"></span><span>Daily value</span></span>",
    ]
    if has_rolling:
        items.append(
            "<span class=\"legend-item\"><span class=\"legend-swatch rolling\"></span><span>7-day rolling average</span></span>"
        )
    items.append(
        "<span class=\"legend-item\"><span class=\"legend-swatch baseline\"></span><span>Zero baseline</span></span>"
    )
    return f"<div class=\"chart-legend\">{''.join(items)}</div>"


def _series_points(
    *,
    series: list[dict[str, Any]],
    key: str,
    width: int,
    height: int,
    min_value: float,
    max_value: float,
    padding_x: int,
    padding_y: int,
) -> list[tuple[float, float]]:
    """Return drawable points for one series key."""

    if not series:
        return []
    if len(series) == 1:
        x_positions = [padding_x + width / 2]
    else:
        step = width / (len(series) - 1)
        x_positions = [padding_x + step * idx for idx in range(len(series))]

    points: list[tuple[float, float]] = []
    for idx, row in enumerate(series):
        value = row.get(key)
        if value is None:
            continue
        y = _scale_y(
            value=float(value),
            min_value=min_value,
            max_value=max_value,
            height=height,
            padding_y=padding_y,
        )
        points.append((x_positions[idx], y))
    return points


def _scale_y(*, min_value: float, max_value: float, height: int, padding_y: int, value: float) -> float:
    """Scale one numeric value into the sparkline y-space."""

    if max_value <= min_value:
        return padding_y + height / 2
    ratio = (value - min_value) / (max_value - min_value)
    return padding_y + height - ratio * height


def _path_from_points(points: list[tuple[float, float]]) -> str:
    """Return one SVG path string from ordered points."""

    if not points:
        return ""
    first_x, first_y = points[0]
    commands = [f"M {first_x:.2f} {first_y:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in points[1:])
    return " ".join(commands)


def _format_value(value: object, format_name: str) -> str:
    """Format one metric value for display."""

    if value is None:
        return "No signal"
    numeric = float(value)
    if format_name == "score":
        return f"{numeric:+.2f}"
    return f"{numeric * 100:.1f}%"


def _format_delta(metric: dict[str, Any]) -> str:
    """Format one metric delta for a card."""

    delta = metric.get("delta")
    if delta is None:
        return "No prior baseline"
    numeric = float(delta)
    if metric["format"] == "score":
        return f"Delta {numeric:+.2f}"
    return f"Delta {numeric * 100:+.1f} pts"


def _sample_label(metric: dict[str, Any]) -> str:
    """Return one metric-specific sample label."""

    sample_count = int(metric["sample_count"])
    if metric["name"] == "Utility score trend":
        return f"{sample_count} votes"
    if metric["name"] == "Utility follow-through":
        return f"{sample_count} opportunities"
    if metric["name"] == "Zero-result read rate":
        return f"{sample_count} reads"
    return f"{sample_count} writes"


def _tone_for_metric(metric: dict[str, Any]) -> str:
    """Return one tone class for a metric card."""

    delta = metric.get("delta")
    if delta is None:
        return "tone-info"
    numeric = float(delta)
    if metric["name"] == "Zero-result read rate":
        if numeric >= 0.05:
            return "tone-danger"
        if numeric < 0:
            return "tone-positive"
        return "tone-info"
    if numeric <= -0.10:
        return "tone-danger"
    if numeric > 0:
        return "tone-positive"
    return "tone-info"


def _tone_for_status(status: str) -> str:
    """Return the tone class for one snapshot status."""

    if status == "healthy":
        return "tone-positive"
    if status == "slipping":
        return "tone-danger"
    return "tone-warning"


def _status_title(status: str) -> str:
    """Return one human title for a snapshot status."""

    if status == "healthy":
        return "Learning loop healthy"
    if status == "slipping":
        return "Learning loop slipping"
    return "Signal still thin"
