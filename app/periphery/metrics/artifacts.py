"""Artifact helpers for generated metrics snapshots and dashboards."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from app.boot.home import get_shellbrain_home


_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def get_metrics_root_dir() -> Path:
    """Return the machine-owned root directory for metrics browser artifacts."""

    return get_shellbrain_home() / "reports" / "metrics"


def get_metrics_artifact_dir(*, repo_id: str) -> Path:
    """Return the machine-owned artifact directory for one repo's metrics outputs."""

    normalized = _NON_ALNUM.sub("-", repo_id.lower()).strip("-") or "repo"
    digest = hashlib.sha1(repo_id.encode("utf-8")).hexdigest()[:8]
    return get_metrics_root_dir() / f"{normalized}-{digest}"


def write_metrics_artifacts(*, repo_id: str, snapshot: dict[str, Any], html: str) -> dict[str, Path]:
    """Write the latest metrics snapshot, markdown summary, and dashboard HTML."""

    artifact_dir = get_metrics_artifact_dir(repo_id=repo_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    json_path = artifact_dir / "latest.json"
    md_path = artifact_dir / "latest.md"
    html_path = artifact_dir / "dashboard.html"

    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(str(snapshot["summary_md"]).strip() + "\n", encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")

    return {
        "artifact_dir": artifact_dir,
        "json_path": json_path,
        "md_path": md_path,
        "html_path": html_path,
    }


def write_metrics_index_artifact(*, html: str) -> Path:
    """Write the combined browser dashboard for all repo metrics snapshots."""

    artifact_dir = get_metrics_root_dir()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    html_path = artifact_dir / "index.html"
    html_path.write_text(html, encoding="utf-8")
    return html_path
