"""Unit coverage for immediate explicit teaching orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from app.core.entities.episodes import Episode
from app.core.entities.identity import CallerIdentity, IdentityTrustLevel
from app.core.entities.inner_agents import TeachKnowledgeSettings
from app.core.entities.knowledge_builder import (
    KnowledgeBuildRunStatus,
    KnowledgeBuildTrigger,
)
from app.core.ports.host_apps.inner_agents import BuildKnowledgeAgentResult
from app.core.use_cases.knowledge_builder.teach_knowledge import (
    TeachKnowledgeRequest,
    execute_teach_knowledge,
)


def test_teach_knowledge_appends_teaching_event_and_runs_provider() -> None:
    """teach should store teaching evidence before invoking the teach agent."""

    uow = _FakeUnitOfWork()
    runner = _FakeTeachRunner()

    result = execute_teach_knowledge(
        _request(),
        uow_factory=lambda: uow,
        clock=_FakeClock(),
        id_generator=_FakeIdGenerator(),
        settings=_settings(),
        agent_runner=runner,
        caller_identity=CallerIdentity(
            host_app="codex",
            host_session_key="thread-1",
            trust_level=IdentityTrustLevel.TRUSTED,
        ),
    )

    assert result.status is KnowledgeBuildRunStatus.OK
    assert result.episode_id == "episode-1"
    assert result.teaching_event_id == "event-1"
    assert result.teaching_event_seq == 1
    assert result.run_id == "run-1"
    assert result.write_count == 1
    assert runner.request is not None
    assert runner.request.teaching_text == "Startup wires dependencies only."
    assert runner.request.teaching_event_id == "event-1"
    assert runner.request.teaching_event_seq == 1
    assert runner.request.current_problem["goal"] == "record architecture rule"
    assert uow.episodes.thread_id == "codex:thread-1"
    assert uow.episodes.episode.host_app == "codex"
    assert len(uow.episodes.events) == 1
    event = uow.episodes.events[0]
    assert event.host_event_key == "teach:event-1"
    assert event.source.value == "user"
    content = json.loads(event.content)
    assert content == {
        "event_type": "teaching",
        "text": "Startup wires dependencies only.",
        "current_problem": {
            "goal": "record architecture rule",
            "surface": "startup",
            "obstacle": "agents may put behavior in startup",
            "hypothesis": "teach should become a durable preference",
        },
        "source_command": "teach",
    }
    assert uow.knowledge_build_runs.added[0].trigger is (
        KnowledgeBuildTrigger.EXPLICIT_TEACH
    )
    assert uow.knowledge_build_runs.added[0].event_watermark == 1
    assert uow.knowledge_build_runs.completed[0]["status"] is (
        KnowledgeBuildRunStatus.OK
    )
    assert uow.knowledge_build_runs.completed[0]["read_trace"] == {
        "commands": ["shellbrain read"]
    }


def test_teach_knowledge_uses_synthetic_episode_without_caller_identity() -> None:
    """teach should still persist evidence when no trusted host session exists."""

    uow = _FakeUnitOfWork()

    result = execute_teach_knowledge(
        _request(),
        uow_factory=lambda: uow,
        clock=_FakeClock(),
        id_generator=_FakeIdGenerator(),
        settings=_settings(),
        agent_runner=_FakeTeachRunner(),
        caller_identity=None,
    )

    assert result.status is KnowledgeBuildRunStatus.OK
    assert uow.episodes.thread_id == "shellbrain:teach"
    assert uow.episodes.episode.host_app == "shellbrain"


def test_teach_knowledge_provider_unavailable_preserves_teaching_event() -> None:
    """provider absence should not discard explicit teaching evidence."""

    uow = _FakeUnitOfWork()

    result = execute_teach_knowledge(
        _request(),
        uow_factory=lambda: uow,
        clock=_FakeClock(),
        id_generator=_FakeIdGenerator(),
        settings=_settings(),
        agent_runner=None,
        caller_identity=None,
    )

    assert result.status is KnowledgeBuildRunStatus.PROVIDER_UNAVAILABLE
    assert result.error_code == "missing_runner"
    assert len(uow.episodes.events) == 1
    assert uow.knowledge_build_runs.completed[0]["status"] is (
        KnowledgeBuildRunStatus.PROVIDER_UNAVAILABLE
    )


def test_teach_request_requires_complete_current_problem() -> None:
    """teach should reject vague context before appending evidence."""

    with pytest.raises(ValueError):
        TeachKnowledgeRequest(
            repo_id="repo-a",
            repo_root="/repo",
            text="Store this.",
            current_problem={
                "goal": "record",
                "surface": "docs",
                "obstacle": "",
                "hypothesis": "none yet",
            },
        )


class _FakeTeachRunner:
    """Provider fake for explicit teach tests."""

    def __init__(self) -> None:
        self.request = None

    def run_teach_knowledge(self, request):
        self.request = request
        return BuildKnowledgeAgentResult(
            status="ok",
            provider=request.provider,
            model=request.model,
            reasoning=request.reasoning,
            input_tokens=100,
            output_tokens=20,
            capture_quality="estimated",
            write_count=1,
            skipped_item_count=0,
            run_summary="Stored explicit teaching.",
            read_trace={"commands": ["shellbrain read"]},
            code_trace={},
        )


class _FakeClock:
    """Deterministic clock."""

    def now(self) -> datetime:
        return datetime(2026, 5, 19, 12, tzinfo=timezone.utc)


class _FakeIdGenerator:
    """Deterministic id generator."""

    def __init__(self) -> None:
        self._ids = iter(("episode-1", "event-1", "run-1"))

    def new_id(self) -> str:
        return next(self._ids)


class _FakeEpisodesRepo:
    """In-memory episode/event repo for teach tests."""

    def __init__(self) -> None:
        self.thread_id = None
        self.episode = None
        self.events = []

    def acquire_thread_sync_guard(self, *, repo_id: str, thread_id: str) -> None:
        del repo_id
        self.thread_id = thread_id

    def get_or_create_episode_for_thread(self, episode: Episode) -> Episode:
        self.episode = episode
        return episode

    def next_event_seq(self, *, episode_id: str) -> int:
        del episode_id
        return len(self.events) + 1

    def append_event(self, event) -> None:
        self.events.append(event)


class _FakeBuildRunsRepo:
    """In-memory build-run repo."""

    def __init__(self) -> None:
        self.added = []
        self.completed = []

    def latest_successful_watermark(self, *, repo_id: str, episode_id: str):
        del repo_id, episode_id
        return None

    def acquire_episode_lock(self, *, repo_id: str, episode_id: str) -> bool:
        del repo_id, episode_id
        return True

    def list_running_runs(self, *, repo_id: str, episode_id: str):
        del repo_id, episode_id
        return ()

    def add(self, run) -> None:
        self.added.append(run)

    def complete(self, **kwargs) -> None:
        self.completed.append(kwargs)


class _FakeUnitOfWork:
    """Minimal context-manager unit of work."""

    def __init__(self) -> None:
        self.episodes = _FakeEpisodesRepo()
        self.knowledge_build_runs = _FakeBuildRunsRepo()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


def _request() -> TeachKnowledgeRequest:
    return TeachKnowledgeRequest(
        repo_id="repo-a",
        repo_root="/repo",
        text="Startup wires dependencies only.",
        current_problem={
            "goal": "record architecture rule",
            "surface": "startup",
            "obstacle": "agents may put behavior in startup",
            "hypothesis": "teach should become a durable preference",
        },
    )


def _settings() -> TeachKnowledgeSettings:
    return TeachKnowledgeSettings(
        provider="codex",
        model="gpt-5.4-mini",
        reasoning="medium",
        timeout_seconds=600,
        max_shellbrain_reads=6,
        max_code_files=5,
        max_write_commands=12,
    )
