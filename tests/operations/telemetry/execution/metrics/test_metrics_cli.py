"""CLI smoke coverage for the metrics dashboard command."""

from __future__ import annotations

import json
from pathlib import Path

from app.periphery.cli import main as cli_main
from app.periphery.cli.hydration import RepoContext


def test_metrics_command_should_open_dashboard_by_default(monkeypatch, tmp_path, capsys) -> None:
    """The command should ask the browser helper to open the generated dashboard by default."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    shellbrain_home = tmp_path / "shellbrain-home"
    monkeypatch.setenv("SHELLBRAIN_HOME", str(shellbrain_home))
    monkeypatch.setattr(
        cli_main,
        "resolve_repo_context",
        lambda **_kwargs: RepoContext(
            repo_root=repo_root,
            repo_id="github.com/example/repo",
            registration_root=repo_root,
        ),
    )
    monkeypatch.setattr(cli_main, "_warn_or_fail_on_unsafe_app_role", lambda: None)
    monkeypatch.setattr(cli_main, "_ensure_repo_registration_for_operation", lambda **_kwargs: None)
    monkeypatch.setattr("app.boot.db.get_optional_db_dsn", lambda: "postgresql://metrics-test")
    monkeypatch.setattr("app.boot.admin_db.get_optional_admin_db_dsn", lambda: None)
    monkeypatch.setattr("app.periphery.db.engine.get_engine", lambda _dsn: object())
    monkeypatch.setattr("app.periphery.metrics.service.build_metrics_snapshot", lambda **_kwargs: _snapshot())

    opened: list[Path] = []
    monkeypatch.setattr(
        "app.periphery.metrics.browser.open_metrics_dashboard",
        lambda path: opened.append(path) or True,
    )

    exit_code = cli_main.main(["metrics"])
    output = capsys.readouterr().out
    artifact_dir = shellbrain_home / "reports" / "metrics"
    dashboard_paths = list(artifact_dir.rglob("dashboard.html"))

    assert exit_code == 0
    assert len(dashboard_paths) == 1
    assert opened == dashboard_paths
    assert "Artifacts: updated in place" in output
    assert "Browser: opened dashboard" in output


def test_metrics_command_should_generate_artifacts_and_skip_browser_when_requested(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    """The command should write all artifacts under Shellbrain home and avoid browser launch when asked."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    shellbrain_home = tmp_path / "shellbrain-home"
    monkeypatch.setenv("SHELLBRAIN_HOME", str(shellbrain_home))
    monkeypatch.setattr(
        cli_main,
        "resolve_repo_context",
        lambda **_kwargs: RepoContext(
            repo_root=repo_root,
            repo_id="github.com/example/repo",
            registration_root=repo_root,
        ),
    )
    monkeypatch.setattr(cli_main, "_warn_or_fail_on_unsafe_app_role", lambda: None)
    monkeypatch.setattr(cli_main, "_ensure_repo_registration_for_operation", lambda **_kwargs: None)
    monkeypatch.setattr("app.boot.db.get_optional_db_dsn", lambda: "postgresql://metrics-test")
    monkeypatch.setattr("app.boot.admin_db.get_optional_admin_db_dsn", lambda: None)
    monkeypatch.setattr("app.periphery.db.engine.get_engine", lambda _dsn: object())
    monkeypatch.setattr("app.periphery.metrics.service.build_metrics_snapshot", lambda **_kwargs: _snapshot())

    opened: list[Path] = []
    monkeypatch.setattr(
        "app.periphery.metrics.browser.open_metrics_dashboard",
        lambda path: opened.append(path) or True,
    )

    exit_code = cli_main.main(["metrics", "--days", "30", "--no-open"])
    output = capsys.readouterr().out
    artifact_root = shellbrain_home / "reports" / "metrics"
    json_paths = list(artifact_root.rglob("latest.json"))
    md_paths = list(artifact_root.rglob("latest.md"))
    html_paths = list(artifact_root.rglob("dashboard.html"))

    assert exit_code == 0
    assert opened == []
    assert len(json_paths) == 1
    assert len(md_paths) == 1
    assert len(html_paths) == 1
    assert not html_paths[0].is_relative_to(repo_root)
    assert json.loads(json_paths[0].read_text(encoding="utf-8"))["repo_id"] == "github.com/example/repo"
    assert "Utility score trend" in md_paths[0].read_text(encoding="utf-8")
    assert "<style>" in html_paths[0].read_text(encoding="utf-8")
    assert "Artifacts: updated in place" in output
    assert "Browser: skipped" in output


def _snapshot() -> dict[str, object]:
    """Return one stable snapshot payload for CLI smoke coverage."""

    return {
        "repo_id": "github.com/example/repo",
        "generated_at": "2026-03-27T15:00:00+00:00",
        "window_days": 30,
        "current_window": {
            "start_at": "2026-02-26T00:00:00+00:00",
            "end_at": "2026-03-27T15:00:00+00:00",
        },
        "previous_window": {
            "start_at": "2026-01-27T09:00:00+00:00",
            "end_at": "2026-02-26T00:00:00+00:00",
        },
        "status": "healthy",
        "confidence": "medium",
        "headline": "Utility score trend is healthy for github.com/example/repo.",
        "alerts": [],
        "metrics": [
            _metric(name="Utility score trend", current=0.6, previous=0.4, delta=0.2, sample_count=12, format_name="score"),
            _metric(name="Utility follow-through", current=0.75, previous=0.5, delta=0.25, sample_count=8, format_name="percent"),
            _metric(name="Zero-result read rate", current=0.1, previous=0.15, delta=-0.05, sample_count=20, format_name="percent"),
            _metric(name="Events-before-write compliance", current=0.9, previous=0.8, delta=0.1, sample_count=20, format_name="percent"),
        ],
        "summary_md": (
            "Utility score trend is healthy for github.com/example/repo, and Utility follow-through stayed stable enough to support a positive read on the current window. "
            "Zero-result read rate is 10.0% now versus 15.0% before and Events-before-write compliance is 90.0% now versus 80.0% before when compared with the previous window. "
            "Watch Utility score trend, Utility follow-through, Zero-result read rate, and Events-before-write compliance next to confirm whether the learning loop is strengthening or just noisy."
        ),
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
    """Return one CLI smoke metric."""

    return {
        "name": name,
        "current": current,
        "previous": previous,
        "delta": delta,
        "sample_count": sample_count,
        "confidence": "medium",
        "format": format_name,
        "daily_series": [
            {"date": "2026-03-26", "value": current - 0.1, "sample_count": sample_count // 2, "rolling_value": current - 0.1},
            {"date": "2026-03-27", "value": current, "sample_count": sample_count - (sample_count // 2), "rolling_value": current - 0.05},
        ],
    }
