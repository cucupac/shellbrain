"""Unit coverage for browser opening helpers."""

from __future__ import annotations

from pathlib import Path

from app.periphery.metrics.browser import open_metrics_dashboard


def test_open_metrics_dashboard_should_open_a_file_uri(monkeypatch, tmp_path: Path) -> None:
    """The browser helper should pass a resolved file URI to webbrowser."""

    captured: dict[str, object] = {}

    def _fake_open(url: str) -> bool:
        captured["url"] = url
        return True

    monkeypatch.setattr("app.periphery.metrics.browser.webbrowser.open", _fake_open)

    dashboard_path = tmp_path / "dashboard.html"
    dashboard_path.write_text("<html></html>", encoding="utf-8")

    result = open_metrics_dashboard(dashboard_path)

    assert result is True
    assert captured["url"] == dashboard_path.resolve().as_uri()
