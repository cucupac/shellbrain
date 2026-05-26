"""Repo-local shadow Git storage adapter."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

from app.core.entities.snapshots import (
    ShadowGitCaptureRequest,
    ShadowGitCaptureResult,
    ShadowGitCaptureState,
    ShadowGitDiffResult,
    ShadowGitPathChange,
    ShadowGitPathChangeStatus,
)
from app.core.ports.local_state.shadow_git import IShadowGitStore


_SHADOW_REF = "refs/shellbrain/snapshots/main"


class ShadowGitError(RuntimeError):
    """Raised when shadow Git capture cannot complete."""


class ShadowGitStore(IShadowGitStore):
    """Capture repo states in `<repo>/.shellbrain/shadow.git`."""

    def capture_snapshot(
        self, request: ShadowGitCaptureRequest
    ) -> ShadowGitCaptureResult:
        """Capture the current repo tree into shadow Git."""

        repo_root = _resolve_git_root(Path(request.repo_root))
        shadow_git_dir = _ensure_shadow_git(repo_root)
        parent_commit = _current_shadow_commit(shadow_git_dir)
        tracked_paths = _list_repo_paths(repo_root)
        with tempfile.TemporaryDirectory(prefix="shellbrain-shadow-index-") as tmpdir:
            index_path = Path(tmpdir) / "index"
            env = {**os.environ, "GIT_INDEX_FILE": str(index_path)}
            _git(
                ["--git-dir", str(shadow_git_dir), "--work-tree", str(repo_root), "read-tree", "--empty"],
                env=env,
            )
            for chunk in _chunks(tracked_paths, size=100):
                _git(
                    [
                        "--git-dir",
                        str(shadow_git_dir),
                        "--work-tree",
                        str(repo_root),
                        "add",
                        "--",
                        *chunk,
                    ],
                    env=env,
                )
            tree_sha = _git(
                [
                    "--git-dir",
                    str(shadow_git_dir),
                    "--work-tree",
                    str(repo_root),
                    "write-tree",
                ],
                env=env,
            ).stdout.strip()

        if parent_commit is not None:
            parent_tree = _git(
                ["--git-dir", str(shadow_git_dir), "rev-parse", f"{parent_commit}^{{tree}}"]
            ).stdout.strip()
            if tree_sha == parent_tree:
                return ShadowGitCaptureResult(
                    state=ShadowGitCaptureState.NOOP,
                    shadow_commit_sha=parent_commit,
                    parent_shadow_commit_sha=parent_commit,
                    changed_paths=(),
                    tree_sha=tree_sha,
                )

        commit_sha = _commit_tree(
            shadow_git_dir=shadow_git_dir,
            tree_sha=tree_sha,
            parent_commit=parent_commit,
            message=_commit_message(request),
        )
        _git(["--git-dir", str(shadow_git_dir), "update-ref", _SHADOW_REF, commit_sha])
        return ShadowGitCaptureResult(
            state=ShadowGitCaptureState.CREATED,
            shadow_commit_sha=commit_sha,
            parent_shadow_commit_sha=parent_commit,
            changed_paths=_changed_paths(
                shadow_git_dir=shadow_git_dir,
                commit_sha=commit_sha,
                parent_commit=parent_commit,
            ),
            tree_sha=tree_sha,
        )

    def diff_snapshot_pair(
        self, *, repo_root: str, base_commit_sha: str, final_commit_sha: str
    ) -> ShadowGitDiffResult:
        """Return a stable patch hash and changed paths for two shadow commits."""

        shadow_git_dir = _shadow_git_dir(_resolve_git_root(Path(repo_root)))
        if not shadow_git_dir.exists():
            raise ShadowGitError(f"shadow.git does not exist: {shadow_git_dir}")
        diff = _git_bytes(
            [
                "--git-dir",
                str(shadow_git_dir),
                "diff",
                "--binary",
                base_commit_sha,
                final_commit_sha,
            ]
        )
        return ShadowGitDiffResult(
            patch_sha=hashlib.sha256(diff).hexdigest(),
            path_changes=_diff_path_changes(
                shadow_git_dir=shadow_git_dir,
                base_commit_sha=base_commit_sha,
                final_commit_sha=final_commit_sha,
            ),
        )


def _resolve_git_root(path: Path) -> Path:
    """Return the Git worktree root for one path."""

    if not path.exists():
        raise ShadowGitError(f"repo_root does not exist: {path}")
    result = _git(["-C", str(path), "rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip()).resolve()


def _shadow_git_dir(repo_root: Path) -> Path:
    return repo_root / ".shellbrain" / "shadow.git"


def _ensure_shadow_git(repo_root: Path) -> Path:
    """Create the repo-local bare shadow store when missing."""

    shadow_git_dir = _shadow_git_dir(repo_root)
    if not shadow_git_dir.exists():
        shadow_git_dir.parent.mkdir(parents=True, exist_ok=True)
        _git(["init", "--bare", str(shadow_git_dir)])
    return shadow_git_dir


def _current_shadow_commit(shadow_git_dir: Path) -> str | None:
    result = _git(
        ["--git-dir", str(shadow_git_dir), "rev-parse", "--verify", "-q", _SHADOW_REF],
        check=False,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _list_repo_paths(repo_root: Path) -> tuple[str, ...]:
    """Return tracked plus untracked non-ignored file paths for capture."""

    output = _git(
        ["-C", str(repo_root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"]
    ).stdout
    paths = []
    for raw_path in output.split("\0"):
        if not raw_path:
            continue
        if _is_excluded_path(raw_path):
            continue
        full_path = repo_root / raw_path
        if not full_path.exists() and not full_path.is_symlink():
            continue
        if full_path.is_dir() and not full_path.is_symlink():
            continue
        paths.append(raw_path)
    return tuple(paths)


def _is_excluded_path(path: str) -> bool:
    return (
        path == ".git"
        or path.startswith(".git/")
        or path == ".shellbrain"
        or path.startswith(".shellbrain/")
    )


def _commit_tree(
    *,
    shadow_git_dir: Path,
    tree_sha: str,
    parent_commit: str | None,
    message: str,
) -> str:
    command = ["--git-dir", str(shadow_git_dir), "commit-tree", tree_sha]
    if parent_commit is not None:
        command.extend(["-p", parent_commit])
    result = _git(
        command,
        input_text=message,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Shellbrain",
            "GIT_AUTHOR_EMAIL": "shellbrain@local",
            "GIT_COMMITTER_NAME": "Shellbrain",
            "GIT_COMMITTER_EMAIL": "shellbrain@local",
        },
    )
    return result.stdout.strip()


def _commit_message(request: ShadowGitCaptureRequest) -> str:
    """Return a compact shadow commit message."""

    parts = [
        "shellbrain snapshot",
        f"snapshot_id={request.snapshot_id}",
        f"repo_id={request.repo_id}",
        f"reason={request.reason.value}",
    ]
    if request.episode_id is not None:
        parts.append(f"episode_id={request.episode_id}")
    if request.captured_after_event_seq is not None:
        parts.append(f"captured_after_event_seq={request.captured_after_event_seq}")
    if request.operation_invocation_id is not None:
        parts.append(f"operation_invocation_id={request.operation_invocation_id}")
    return "\n".join(parts) + "\n"


def _changed_paths(
    *, shadow_git_dir: Path, commit_sha: str, parent_commit: str | None
) -> tuple[str, ...]:
    if parent_commit is None:
        output = _git(
            [
                "--git-dir",
                str(shadow_git_dir),
                "ls-tree",
                "-r",
                "-z",
                "--name-only",
                commit_sha,
            ]
        ).stdout
        return tuple(path for path in output.split("\0") if path)
    return _diff_changed_paths(
        shadow_git_dir=shadow_git_dir,
        base_commit_sha=parent_commit,
        final_commit_sha=commit_sha,
    )


def _diff_changed_paths(
    *, shadow_git_dir: Path, base_commit_sha: str, final_commit_sha: str
) -> tuple[str, ...]:
    return tuple(
        change.path
        for change in _diff_path_changes(
            shadow_git_dir=shadow_git_dir,
            base_commit_sha=base_commit_sha,
            final_commit_sha=final_commit_sha,
        )
    )


def _diff_path_changes(
    *, shadow_git_dir: Path, base_commit_sha: str, final_commit_sha: str
) -> tuple[ShadowGitPathChange, ...]:
    output = _git(
        [
            "--git-dir",
            str(shadow_git_dir),
            "diff",
            "--name-status",
            "--find-renames",
            "-z",
            base_commit_sha,
            final_commit_sha,
        ]
    ).stdout
    fields = [field for field in output.split("\0") if field]
    changes: list[ShadowGitPathChange] = []
    index = 0
    while index < len(fields):
        status_code = fields[index]
        index += 1
        if status_code.startswith("R"):
            if index + 1 >= len(fields):
                raise ShadowGitError("malformed rename status from shadow Git diff")
            old_path = fields[index]
            new_path = fields[index + 1]
            index += 2
            changes.append(
                ShadowGitPathChange(
                    status=ShadowGitPathChangeStatus.RENAMED,
                    path=new_path,
                    old_path=old_path,
                )
            )
            continue
        if index >= len(fields):
            raise ShadowGitError("malformed path status from shadow Git diff")
        path = fields[index]
        index += 1
        changes.append(
            ShadowGitPathChange(
                status=_path_change_status(status_code),
                path=path,
            )
        )
    return tuple(changes)


def _path_change_status(status_code: str) -> ShadowGitPathChangeStatus:
    if status_code == "A":
        return ShadowGitPathChangeStatus.ADDED
    if status_code == "M":
        return ShadowGitPathChangeStatus.MODIFIED
    if status_code == "D":
        return ShadowGitPathChangeStatus.DELETED
    raise ShadowGitError(f"unsupported shadow Git diff status: {status_code}")


def _chunks(paths: tuple[str, ...], *, size: int):
    for index in range(0, len(paths), size):
        yield paths[index : index + size]


def _git(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        input=input_text,
        env=env,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise ShadowGitError(f"git {' '.join(args)} failed: {stderr}")
    return result


def _git_bytes(args: list[str]) -> bytes:
    result = subprocess.run(["git", *args], capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        raise ShadowGitError(f"git {' '.join(args)} failed: {stderr or stdout}")
    return result.stdout
