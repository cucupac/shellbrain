"""Poller trigger coverage for build_knowledge lifecycle runs."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

from app.core.entities.knowledge_builder import KnowledgeBuildTrigger
from app.infrastructure.process.episode_sync.poller import run_episode_poller


def test_poller_runs_build_knowledge_for_idle_stable_episode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """idle-stable poller exit should consolidate active known episodes."""

    calls: list[dict[str, object]] = []
    _patch_common_poller_edges(monkeypatch)
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.discover_active_host_session",
        lambda **kwargs: {
            "host_app": "codex",
            "host_session_key": "thread-1",
            "transcript_path": tmp_path / "codex.jsonl",
            "updated_at": 1.0,
        },
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.sync_episode_from_host",
        lambda **kwargs: _sync_result("ep-1", "codex:thread-1", tmp_path),
    )

    run_episode_poller(
        repo_id="repo-a",
        repo_root=tmp_path,
        uow_factory=lambda: nullcontext(object()),
        run_build_knowledge=lambda **kwargs: calls.append(kwargs),
        idle_stable_seconds=0,
    )

    assert calls == [
        {
            "repo_id": "repo-a",
            "repo_root": tmp_path.resolve(),
            "episode_id": "ep-1",
            "trigger": KnowledgeBuildTrigger.IDLE_STABLE,
        }
    ]


def test_poller_runs_build_knowledge_for_replaced_episode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """session replacement should run build_knowledge for the old episode."""

    calls: list[dict[str, object]] = []
    discoveries = {"count": 0}
    _patch_common_poller_edges(monkeypatch)
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller._close_episode",
        lambda **kwargs: "ep-old",
    )

    def _discover(**kwargs):
        discoveries["count"] += 1
        suffix = "old" if discoveries["count"] == 1 else "new"
        return {
            "host_app": "codex",
            "host_session_key": f"thread-{suffix}",
            "transcript_path": tmp_path / f"codex-{suffix}.jsonl",
            "updated_at": 1.0 if suffix == "old" else 2.0,
        }

    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.discover_active_host_session",
        _discover,
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.sync_episode_from_host",
        lambda **kwargs: _sync_result(
            "ep-new" if "thread-new" in kwargs["host_session_key"] else "ep-old",
            f"codex:{kwargs['host_session_key']}",
            tmp_path,
        ),
    )

    run_episode_poller(
        repo_id="repo-a",
        repo_root=tmp_path,
        uow_factory=lambda: nullcontext(object()),
        run_build_knowledge=lambda **kwargs: calls.append(kwargs),
        idle_stable_seconds=0,
    )

    assert {
        "repo_id": "repo-a",
        "repo_root": tmp_path.resolve(),
        "episode_id": "ep-old",
        "trigger": KnowledgeBuildTrigger.SESSION_REPLACED,
    } in calls


def _patch_common_poller_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch process and telemetry edges away from poller trigger tests."""

    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.SUPPORTED_HOSTS",
        ("codex",),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.acquire_poller_lock",
        lambda **kwargs: _NoOpLock(),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.write_poller_pid_artifact",
        lambda **kwargs: Path("/tmp/episode_sync.pid"),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.POLL_INTERVAL_SECONDS",
        0,
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.default_search_roots",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.collect_model_usage_records_for_session",
        lambda **kwargs: (),
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller._record_sync_telemetry_best_effort",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "app.infrastructure.process.episode_sync.poller.record_episode_sync_status",
        lambda **kwargs: None,
    )


def _sync_result(episode_id: str, thread_id: str, tmp_path: Path) -> dict[str, object]:
    """Return a poller sync result payload."""

    return {
        "thread_id": thread_id,
        "episode_id": episode_id,
        "transcript_path": str(tmp_path / "transcript.jsonl"),
        "imported_event_count": 1,
        "total_event_count": 1,
        "user_event_count": 1,
        "assistant_event_count": 0,
        "tool_event_count": 0,
        "system_event_count": 0,
        "tool_type_counts": {},
    }


class _NoOpLock:
    """Minimal poller lock test double."""

    def release(self) -> None:
        return None
