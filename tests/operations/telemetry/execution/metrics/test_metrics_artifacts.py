"""Unit coverage for metrics artifact writing."""

from __future__ import annotations

import json

from app.periphery.reporting.metrics.artifacts import (
    get_metrics_artifact_dir,
    get_metrics_root_dir,
    write_metrics_artifacts,
    write_metrics_index_artifact,
)


def test_write_metrics_artifacts_should_write_and_overwrite_latest_outputs(monkeypatch, tmp_path) -> None:
    """Artifacts should always land under Shellbrain home and overwrite latest files in place."""

    shellbrain_home = tmp_path / "shellbrain-home"
    monkeypatch.setenv("SHELLBRAIN_HOME", str(shellbrain_home))

    first_snapshot = {
        "repo_id": "github.com/example/repo",
        "summary_md": "First sentence. Second sentence. Third sentence.",
    }
    second_snapshot = {
        "repo_id": "github.com/example/repo",
        "summary_md": "Updated first sentence. Updated second sentence. Updated third sentence.",
    }

    first_paths = write_metrics_artifacts(
        repo_id="github.com/example/repo",
        snapshot=first_snapshot,
        html="<html><body>first</body></html>",
    )
    second_paths = write_metrics_artifacts(
        repo_id="github.com/example/repo",
        snapshot=second_snapshot,
        html="<html><body>second</body></html>",
    )

    assert first_paths["artifact_dir"] == second_paths["artifact_dir"]
    assert second_paths["artifact_dir"].is_relative_to(shellbrain_home)
    assert json.loads(second_paths["json_path"].read_text(encoding="utf-8"))["summary_md"] == second_snapshot["summary_md"]
    assert second_paths["md_path"].read_text(encoding="utf-8") == second_snapshot["summary_md"] + "\n"
    assert second_paths["html_path"].read_text(encoding="utf-8") == "<html><body>second</body></html>"


def test_get_metrics_artifact_dir_should_normalize_repo_ids(monkeypatch, tmp_path) -> None:
    """Repo slugs should be stable, filesystem-safe, and namespaced by Shellbrain home."""

    shellbrain_home = tmp_path / "shellbrain-home"
    monkeypatch.setenv("SHELLBRAIN_HOME", str(shellbrain_home))

    artifact_dir = get_metrics_artifact_dir(repo_id="GitHub.com/Example Repo")

    assert artifact_dir.parent == shellbrain_home / "reports" / "metrics"
    assert artifact_dir.name.startswith("github-com-example-repo-")


def test_write_metrics_index_artifact_should_write_root_browser_dashboard(monkeypatch, tmp_path) -> None:
    """The combined browser dashboard should live at the metrics root."""

    shellbrain_home = tmp_path / "shellbrain-home"
    monkeypatch.setenv("SHELLBRAIN_HOME", str(shellbrain_home))

    html_path = write_metrics_index_artifact(html="<html><body>overview</body></html>")

    assert html_path == get_metrics_root_dir() / "index.html"
    assert html_path.read_text(encoding="utf-8") == "<html><body>overview</body></html>"
