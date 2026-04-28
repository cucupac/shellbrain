"""CLI smoke coverage for the metrics dashboard command."""

from __future__ import annotations

import json
from pathlib import Path

from app.periphery.cli import main as cli_main


def test_metrics_command_should_generate_all_repo_artifacts_and_launch_viewer(monkeypatch, tmp_path, capsys) -> None:
    """The no-option metrics command should build per-repo artifacts and invoke the terminal viewer."""

    shellbrain_home = tmp_path / "shellbrain-home"
    monkeypatch.setenv("SHELLBRAIN_HOME", str(shellbrain_home))
    monkeypatch.setattr(cli_main, "_warn_or_fail_on_unsafe_app_role", lambda: None)
    monkeypatch.setattr("app.boot.db.get_optional_db_dsn", lambda: "postgresql://metrics-test")
    monkeypatch.setattr("app.boot.admin_db.get_optional_admin_db_dsn", lambda: None)
    monkeypatch.setattr("app.periphery.db.engine.get_engine", lambda _dsn: object())
    monkeypatch.setattr(
        "app.periphery.metrics.service.list_metrics_repo_ids",
        lambda **_kwargs: ["github.com/example/one", "github.com/example/two"],
    )
    monkeypatch.setattr(
        "app.periphery.metrics.service.build_metrics_snapshot",
        lambda **kwargs: _snapshot(repo_id=str(kwargs["repo_id"])),
    )

    opened: list[Path] = []
    monkeypatch.setattr(
        "app.periphery.metrics.browser.open_metrics_dashboard",
        lambda path: opened.append(path) or True,
    )

    viewer_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.periphery.metrics.pager.present_metrics_repo_pager",
        lambda **kwargs: viewer_calls.append(kwargs),
    )

    exit_code = cli_main.main(["metrics"])
    output = capsys.readouterr().out
    artifact_root = shellbrain_home / "reports" / "metrics"
    json_paths = sorted(artifact_root.rglob("latest.json"))
    md_paths = sorted(artifact_root.rglob("latest.md"))
    html_paths = sorted(artifact_root.rglob("dashboard.html"))

    assert exit_code == 0
    assert opened == []
    assert len(json_paths) == 2
    assert len(md_paths) == 2
    assert len(html_paths) == 2
    repo_ids = {json.loads(path.read_text(encoding="utf-8"))["repo_id"] for path in json_paths}
    assert repo_ids == {"github.com/example/one", "github.com/example/two"}
    assert all("Utility score trend" in path.read_text(encoding="utf-8") for path in md_paths)
    assert all("<style>" in path.read_text(encoding="utf-8") for path in html_paths)
    assert len(viewer_calls) == 1
    assert len(viewer_calls[0]["entries"]) == 2
    assert callable(viewer_calls[0]["open_dashboard"])
    assert "Generated Shellbrain metrics for 2 repos" in output
    assert "Window: last 30 days" in output
    assert "Browser: press 'o' in the viewer to open the current dashboard" in output
def test_metrics_command_should_print_empty_message_when_no_repo_metrics_exist(monkeypatch, capsys) -> None:
    """No telemetry repos should return a clean message and no viewer launch."""

    monkeypatch.setattr(cli_main, "_warn_or_fail_on_unsafe_app_role", lambda: None)
    monkeypatch.setattr("app.boot.db.get_optional_db_dsn", lambda: "postgresql://metrics-test")
    monkeypatch.setattr("app.boot.admin_db.get_optional_admin_db_dsn", lambda: None)
    monkeypatch.setattr("app.periphery.db.engine.get_engine", lambda _dsn: object())
    monkeypatch.setattr("app.periphery.metrics.service.list_metrics_repo_ids", lambda **_kwargs: [])
    monkeypatch.setattr(
        "app.periphery.metrics.pager.present_metrics_repo_pager",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("viewer should not run when no repos are present")),
    )

    exit_code = cli_main.main(["metrics"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "No tracked repos found in metrics telemetry yet." in output


def test_metrics_command_should_reject_global_repo_target_options(monkeypatch, capsys) -> None:
    """Metrics should fail fast when legacy repo targeting options are passed globally."""

    monkeypatch.setattr(cli_main, "_warn_or_fail_on_unsafe_app_role", lambda: None)
    monkeypatch.setattr("app.boot.db.get_optional_db_dsn", lambda: "postgresql://metrics-test")
    monkeypatch.setattr("app.boot.admin_db.get_optional_admin_db_dsn", lambda: None)
    monkeypatch.setattr("app.periphery.db.engine.get_engine", lambda _dsn: object())

    exit_code = cli_main.main(["--repo-id", "github.com/example/repo", "metrics"])
    error = capsys.readouterr().err

    assert exit_code == 1
    assert "`shellbrain metrics` does not accept options. Run `shellbrain metrics`." in error


def _snapshot(*, repo_id: str = "github.com/example/repo") -> dict[str, object]:
    """Return one stable snapshot payload for CLI smoke coverage."""

    return {
        "repo_id": repo_id,
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
        "headline": f"Utility score trend is healthy for {repo_id}.",
        "alerts": [],
        "metrics": [
            _metric(name="Utility score trend", current=0.6, previous=0.4, delta=0.2, sample_count=12, format_name="score"),
            _metric(name="Utility follow-through", current=0.75, previous=0.5, delta=0.25, sample_count=8, format_name="percent"),
            _metric(name="Zero-result read rate", current=0.1, previous=0.15, delta=-0.05, sample_count=20, format_name="percent"),
            _metric(name="Events-before-write compliance", current=0.9, previous=0.8, delta=0.1, sample_count=20, format_name="percent"),
        ],
        "summary_md": (
            f"Utility score trend is healthy for {repo_id}, and Utility follow-through stayed stable enough to support a positive read on the current window. "
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
