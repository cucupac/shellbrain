"""Integration coverage for repo-local shadow Git capture."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from app.core.entities.snapshots import (
    ShadowGitCaptureRequest,
    ShadowGitCaptureState,
    ShadowGitPathChangeStatus,
    ShadowSnapshotReason,
)
from app.infrastructure.local_state.shadow_git_store import ShadowGitStore


pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is required")


def test_shadow_git_capture_tracks_untracked_files_and_preserves_user_index(
    tmp_path: Path,
) -> None:
    """Shadow capture should use its own index and exclude runtime/ignored paths."""

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / ".gitignore").write_text(".shellbrain/\nignored.log\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("original\n", encoding="utf-8")
    _git(repo, "add", ".gitignore", "tracked.txt")
    _git(repo, "commit", "-m", "initial")
    (repo / "tracked.txt").write_text("modified\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")
    (repo / "ignored.log").write_text("ignored\n", encoding="utf-8")
    (repo / ".shellbrain").mkdir()
    (repo / ".shellbrain" / "internal.txt").write_text("internal\n", encoding="utf-8")
    status_before = _git(repo, "status", "--porcelain=v1").stdout

    result = ShadowGitStore().capture_snapshot(
        ShadowGitCaptureRequest(
            snapshot_id="snap-1",
            repo_id="repo-a",
            repo_root=str(repo),
            reason=ShadowSnapshotReason.CLOSEOUT,
        )
    )

    assert result.state is ShadowGitCaptureState.CREATED
    assert result.shadow_commit_sha is not None
    assert (repo / ".shellbrain" / "shadow.git").is_dir()
    assert _git(repo, "status", "--porcelain=v1").stdout == status_before
    captured_paths = _shadow_git(
        repo,
        "ls-tree",
        "-r",
        "--name-only",
        result.shadow_commit_sha,
    ).stdout.splitlines()
    assert "tracked.txt" in captured_paths
    assert "new.txt" in captured_paths
    assert "ignored.log" not in captured_paths
    assert ".shellbrain/internal.txt" not in captured_paths

    repeated = ShadowGitStore().capture_snapshot(
        ShadowGitCaptureRequest(
            snapshot_id="snap-2",
            repo_id="repo-a",
            repo_root=str(repo),
            reason=ShadowSnapshotReason.CLOSEOUT,
        )
    )

    assert repeated.state is ShadowGitCaptureState.NOOP
    assert repeated.shadow_commit_sha == result.shadow_commit_sha


def test_shadow_git_capture_includes_tracked_ignored_files(tmp_path: Path) -> None:
    """Tracked ignored files should capture without adding ignored local files."""

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / ".gitignore").write_text(".shellbrain/\n.husky/\n", encoding="utf-8")
    husky_dir = repo / ".husky"
    husky_dir.mkdir()
    (husky_dir / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    _git(repo, "add", ".gitignore")
    _git(repo, "add", "-f", ".husky/pre-commit")
    _git(repo, "commit", "-m", "initial")
    (husky_dir / "local-hook").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")

    result = ShadowGitStore().capture_snapshot(
        ShadowGitCaptureRequest(
            snapshot_id="snap-ignored-tracked",
            repo_id="repo-a",
            repo_root=str(repo),
            reason=ShadowSnapshotReason.BASELINE,
        )
    )

    assert result.state is ShadowGitCaptureState.CREATED
    assert result.shadow_commit_sha is not None
    captured_paths = _shadow_git(
        repo,
        "ls-tree",
        "-r",
        "--name-only",
        result.shadow_commit_sha,
    ).stdout.splitlines()
    assert ".husky/pre-commit" in captured_paths
    assert ".husky/local-hook" not in captured_paths


def test_shadow_git_capture_represents_deleted_tracked_files(tmp_path: Path) -> None:
    """Deleted tracked files should disappear from the new shadow tree."""

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / ".gitignore").write_text(".shellbrain/\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("original\n", encoding="utf-8")
    _git(repo, "add", ".gitignore", "tracked.txt")
    _git(repo, "commit", "-m", "initial")
    store = ShadowGitStore()
    first = store.capture_snapshot(
        ShadowGitCaptureRequest(
            snapshot_id="snap-1",
            repo_id="repo-a",
            repo_root=str(repo),
            reason=ShadowSnapshotReason.BASELINE,
        )
    )
    (repo / "tracked.txt").unlink()

    second = store.capture_snapshot(
        ShadowGitCaptureRequest(
            snapshot_id="snap-2",
            repo_id="repo-a",
            repo_root=str(repo),
            reason=ShadowSnapshotReason.CLOSEOUT,
        )
    )

    assert first.shadow_commit_sha != second.shadow_commit_sha
    assert second.changed_paths == ("tracked.txt",)
    captured_paths = _shadow_git(
        repo,
        "ls-tree",
        "-r",
        "--name-only",
        second.shadow_commit_sha,
    ).stdout.splitlines()
    assert "tracked.txt" not in captured_paths


def test_shadow_git_diff_reports_path_change_statuses(tmp_path: Path) -> None:
    """Shadow diffs should expose added, modified, deleted, and renamed paths."""

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / ".gitignore").write_text(".shellbrain/\n", encoding="utf-8")
    (repo / "modified.txt").write_text("before\n", encoding="utf-8")
    (repo / "deleted.txt").write_text("delete me\n", encoding="utf-8")
    (repo / "old-name.txt").write_text("same content\n", encoding="utf-8")
    _git(repo, "add", ".gitignore", "modified.txt", "deleted.txt", "old-name.txt")
    _git(repo, "commit", "-m", "initial")
    store = ShadowGitStore()
    base = store.capture_snapshot(
        ShadowGitCaptureRequest(
            snapshot_id="snap-base",
            repo_id="repo-a",
            repo_root=str(repo),
            reason=ShadowSnapshotReason.BASELINE,
        )
    )
    (repo / "modified.txt").write_text("after\n", encoding="utf-8")
    (repo / "deleted.txt").unlink()
    (repo / "old-name.txt").rename(repo / "new-name.txt")
    (repo / "added.txt").write_text("new\n", encoding="utf-8")
    final = store.capture_snapshot(
        ShadowGitCaptureRequest(
            snapshot_id="snap-final",
            repo_id="repo-a",
            repo_root=str(repo),
            reason=ShadowSnapshotReason.CLOSEOUT,
        )
    )

    assert base.shadow_commit_sha is not None
    assert final.shadow_commit_sha is not None
    diff = store.diff_snapshot_pair(
        repo_root=str(repo),
        base_commit_sha=base.shadow_commit_sha,
        final_commit_sha=final.shadow_commit_sha,
    )

    actual = {
        (change.status, change.path, change.old_path) for change in diff.path_changes
    }
    assert (
        ShadowGitPathChangeStatus.ADDED,
        "added.txt",
        None,
    ) in actual
    assert (
        ShadowGitPathChangeStatus.MODIFIED,
        "modified.txt",
        None,
    ) in actual
    assert (
        ShadowGitPathChangeStatus.DELETED,
        "deleted.txt",
        None,
    ) in actual
    assert (
        ShadowGitPathChangeStatus.RENAMED,
        "new-name.txt",
        "old-name.txt",
    ) in actual
    assert "new-name.txt" in diff.changed_paths


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _shadow_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "--git-dir", str(repo / ".shellbrain" / "shadow.git"), *args],
        check=True,
        capture_output=True,
        text=True,
    )
