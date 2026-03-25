"""High-level behavior contracts for poller singleton ownership."""

from __future__ import annotations

import json
from pathlib import Path
import socket

from app.periphery.episodes.launcher import ensure_episode_sync_started
from app.periphery.episodes.poller_lock import acquire_poller_lock, inspect_poller_lock


def test_first_poller_lock_acquisition_writes_owner_metadata(tmp_path: Path) -> None:
    """first poller lock acquisition should always persist one owner payload."""

    repo_root = _make_repo_root(tmp_path)

    handle = acquire_poller_lock(repo_id="repo-a", repo_root=repo_root)

    assert handle is not None
    inspection = inspect_poller_lock(repo_root=repo_root)
    assert inspection.status == "active"
    assert inspection.owner is not None
    assert inspection.owner["repo_id"] == "repo-a"
    assert inspection.owner["repo_root"] == str(repo_root.resolve())
    assert isinstance(inspection.owner["pid"], int)
    assert isinstance(inspection.owner["hostname"], str)
    assert isinstance(inspection.owner["started_at"], str)

    owner_path = repo_root / ".shellbrain" / "episode_sync.lock" / "owner.json"
    assert json.loads(owner_path.read_text(encoding="utf-8")) == inspection.owner

    handle.release()
    assert inspect_poller_lock(repo_root=repo_root).status == "unlocked"


def test_second_poller_lock_acquisition_returns_none_while_owner_is_alive(tmp_path: Path) -> None:
    """second poller lock acquisition should always return none while one live owner exists."""

    repo_root = _make_repo_root(tmp_path)
    handle = acquire_poller_lock(repo_id="repo-a", repo_root=repo_root)

    assert handle is not None
    assert acquire_poller_lock(repo_id="repo-a", repo_root=repo_root) is None

    handle.release()


def test_stale_poller_lock_is_removed_and_reacquired(tmp_path: Path, monkeypatch) -> None:
    """stale poller lock should always be cleared and reacquired."""

    repo_root = _make_repo_root(tmp_path)
    lock_root = repo_root / ".shellbrain" / "episode_sync.lock"
    lock_root.mkdir(parents=True, exist_ok=True)
    (lock_root / "owner.json").write_text(
        json.dumps(
            {
                "hostname": socket.gethostname().strip().lower(),
                "pid": 999_999,
                "repo_id": "repo-a",
                "repo_root": str(repo_root.resolve()),
                "started_at": "2026-03-24T00:00:00+00:00",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.periphery.episodes.poller_lock._is_process_running", lambda pid: False)

    handle = acquire_poller_lock(repo_id="repo-a", repo_root=repo_root)

    assert handle is not None
    inspection = inspect_poller_lock(repo_root=repo_root)
    assert inspection.status == "active"
    assert inspection.owner == handle.owner
    assert inspection.owner["pid"] != 999_999

    handle.release()


def test_permission_denied_pid_probe_should_still_count_as_active(tmp_path: Path, monkeypatch) -> None:
    """permission-denied pid probes should still preserve the active singleton lock."""

    repo_root = _make_repo_root(tmp_path)
    lock_root = repo_root / ".shellbrain" / "episode_sync.lock"
    lock_root.mkdir(parents=True, exist_ok=True)
    owner = {
        "hostname": socket.gethostname().strip().lower(),
        "pid": 4242,
        "repo_id": "repo-a",
        "repo_root": str(repo_root.resolve()),
        "started_at": "2026-03-24T00:00:00+00:00",
    }
    (lock_root / "owner.json").write_text(json.dumps(owner, indent=2, sort_keys=True), encoding="utf-8")

    def _raise_permission_error(_pid: int) -> None:
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr("app.periphery.episodes.poller_lock.os.kill", _raise_permission_error)

    inspection = inspect_poller_lock(repo_root=repo_root)

    assert inspection.status == "active"
    assert inspection.owner == owner


def test_launcher_does_not_spawn_when_an_active_lock_exists(tmp_path: Path, monkeypatch) -> None:
    """launcher should always skip spawn when one active poller lock already exists."""

    repo_root = _make_repo_root(tmp_path)
    handle = acquire_poller_lock(repo_id="repo-a", repo_root=repo_root)

    assert handle is not None

    def _unexpected_spawn(*args, **kwargs):
        raise AssertionError("launcher should not spawn a second poller while the lock is active")

    monkeypatch.setattr("app.periphery.episodes.launcher.subprocess.Popen", _unexpected_spawn)

    assert ensure_episode_sync_started(repo_id="repo-a", repo_root=repo_root) is False

    handle.release()


def test_launcher_spawns_when_no_active_lock_exists(tmp_path: Path, monkeypatch) -> None:
    """launcher should always spawn one poller when no active lock exists."""

    repo_root = _make_repo_root(tmp_path)
    calls: list[tuple[list[str], dict[str, object]]] = []

    class _FakeProcess:
        pid = 4242

    def _fake_popen(command, **kwargs):
        calls.append((command, kwargs))
        return _FakeProcess()

    monkeypatch.setattr("app.periphery.episodes.launcher.subprocess.Popen", _fake_popen)

    assert ensure_episode_sync_started(repo_id="repo-a", repo_root=repo_root) is True
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[1:3] == ["-m", "app.periphery.episodes.poller"]
    assert command[-2:] == ["--repo-root", str(repo_root.resolve())]
    assert kwargs["cwd"] == repo_root.resolve()


def _make_repo_root(tmp_path: Path) -> Path:
    """Create one isolated repo root used for singleton lock tests."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root
