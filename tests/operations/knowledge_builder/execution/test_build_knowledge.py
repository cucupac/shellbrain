"""Unit coverage for build_knowledge lifecycle orchestration."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.entities.episodes import Episode, EpisodeStatus
from app.core.entities.inner_agents import BuildKnowledgeSettings
from app.core.entities.knowledge_builder import (
    KnowledgeBuildRun,
    KnowledgeBuildRunStatus,
    KnowledgeBuildTrigger,
)
from app.core.ports.host_apps.inner_agents import BuildKnowledgeAgentResult
from app.core.use_cases.knowledge_builder.build_knowledge import (
    BuildKnowledgeRequest,
    execute_build_knowledge,
)


def test_build_knowledge_records_successful_run_for_new_events() -> None:
    """build_knowledge should run provider and persist final counts."""

    uow = _FakeUnitOfWork(event_watermark=7, latest_success=3)
    runner = _FakeBuildKnowledgeRunner()

    result = execute_build_knowledge(
        _request(trigger=KnowledgeBuildTrigger.SESSION_REPLACED),
        uow_factory=lambda: uow,
        clock=_FakeClock(),
        id_generator=_FakeIdGenerator(),
        settings=_settings(),
        agent_runner=runner,
    )

    assert result.status is KnowledgeBuildRunStatus.OK
    assert result.run_id == "run-1"
    assert result.event_watermark == 7
    assert result.previous_event_watermark == 3
    assert result.write_count == 2
    assert result.run_summary == "Wrote useful knowledge."
    assert runner.request is not None
    assert runner.request.episode_id == "episode-1"
    assert runner.request.trigger == "session_replaced"
    assert uow.knowledge_build_runs.added[0].status is KnowledgeBuildRunStatus.RUNNING
    assert uow.knowledge_build_runs.completed[0]["status"] is KnowledgeBuildRunStatus.OK


def test_build_knowledge_skips_when_no_new_events() -> None:
    """build_knowledge should not invoke provider when watermark is already current."""

    uow = _FakeUnitOfWork(event_watermark=7, latest_success=7)
    runner = _FakeBuildKnowledgeRunner()

    result = execute_build_knowledge(
        _request(),
        uow_factory=lambda: uow,
        clock=_FakeClock(),
        id_generator=_FakeIdGenerator(),
        settings=_settings(),
        agent_runner=runner,
    )

    assert result.status is KnowledgeBuildRunStatus.SKIPPED
    assert result.error_code == "no_new_events"
    assert runner.request is None
    assert uow.knowledge_build_runs.added == []


def test_build_knowledge_records_provider_unavailable() -> None:
    """provider absence should create and finalize one failed run."""

    uow = _FakeUnitOfWork(event_watermark=5, latest_success=None)

    result = execute_build_knowledge(
        _request(),
        uow_factory=lambda: uow,
        clock=_FakeClock(),
        id_generator=_FakeIdGenerator(),
        settings=_settings(),
        agent_runner=None,
    )

    assert result.status is KnowledgeBuildRunStatus.PROVIDER_UNAVAILABLE
    assert result.error_code == "missing_runner"
    assert uow.knowledge_build_runs.completed[0]["status"] is (
        KnowledgeBuildRunStatus.PROVIDER_UNAVAILABLE
    )


def test_build_knowledge_skips_when_existing_run_is_running() -> None:
    """running build rows should prevent duplicate provider work."""

    uow = _FakeUnitOfWork(
        event_watermark=5,
        latest_success=None,
        running_runs=(
            _running_run(
                started_at=datetime(2026, 5, 12, 23, 30, tzinfo=timezone.utc)
            ),
        ),
    )
    runner = _FakeBuildKnowledgeRunner()

    result = execute_build_knowledge(
        _request(),
        uow_factory=lambda: uow,
        clock=_FakeClock(),
        id_generator=_FakeIdGenerator(),
        settings=_settings(),
        agent_runner=runner,
    )

    assert result.status is KnowledgeBuildRunStatus.SKIPPED
    assert result.error_code == "build_already_running"
    assert runner.request is None
    assert uow.knowledge_build_runs.completed == []


def test_build_knowledge_times_out_stale_running_run_before_new_run() -> None:
    """stale running build rows should be finalized before new provider work starts."""

    uow = _FakeUnitOfWork(
        event_watermark=5,
        latest_success=None,
        running_runs=(
            _running_run(
                run_id="stale-run",
                started_at=datetime(2026, 5, 12, 23, 0, tzinfo=timezone.utc),
            ),
        ),
    )
    runner = _FakeBuildKnowledgeRunner()

    result = execute_build_knowledge(
        _request(),
        uow_factory=lambda: uow,
        clock=_FakeClock(),
        id_generator=_FakeIdGenerator(),
        settings=_settings(),
        agent_runner=runner,
    )

    assert result.status is KnowledgeBuildRunStatus.OK
    assert uow.knowledge_build_runs.completed[0]["run_id"] == "stale-run"
    assert uow.knowledge_build_runs.completed[0]["status"] is (
        KnowledgeBuildRunStatus.TIMEOUT
    )
    assert uow.knowledge_build_runs.completed[0]["error_code"] == "stale_running_run"
    assert uow.knowledge_build_runs.added[0].id == "run-1"
    assert runner.request is not None


class _FakeBuildKnowledgeRunner:
    """Provider fake for build_knowledge tests."""

    def __init__(self) -> None:
        self.request = None

    def run_build_knowledge(self, request):
        self.request = request
        return BuildKnowledgeAgentResult(
            status="ok",
            provider=request.provider,
            model=request.model,
            reasoning=request.reasoning,
            write_count=2,
            skipped_item_count=1,
            run_summary="Wrote useful knowledge.",
        )


class _FakeClock:
    """Deterministic clock."""

    def now(self) -> datetime:
        return datetime(2026, 5, 13, tzinfo=timezone.utc)


class _FakeIdGenerator:
    """Deterministic id generator."""

    def new_id(self) -> str:
        return "run-1"


class _FakeEpisodesRepo:
    """Minimal episode repo for build_knowledge tests."""

    def __init__(self, *, event_watermark: int) -> None:
        self._event_watermark = event_watermark

    def get_episode(self, *, repo_id: str, episode_id: str):
        return Episode(
            id=episode_id,
            repo_id=repo_id,
            host_app="codex",
            thread_id="codex:thread-1",
            status=EpisodeStatus.ACTIVE,
        )

    def event_watermark(self, *, repo_id: str, episode_id: str) -> int:
        del repo_id, episode_id
        return self._event_watermark


class _FakeBuildRunsRepo:
    """In-memory build-run repo."""

    def __init__(
        self,
        *,
        latest_success: int | None,
        locked: bool = True,
        running_runs: tuple[KnowledgeBuildRun, ...] = (),
    ) -> None:
        self._latest_success = latest_success
        self._locked = locked
        self._running_runs = running_runs
        self.added = []
        self.completed = []

    def acquire_episode_lock(self, *, repo_id: str, episode_id: str) -> bool:
        del repo_id, episode_id
        return self._locked

    def latest_successful_watermark(self, *, repo_id: str, episode_id: str):
        del repo_id, episode_id
        return self._latest_success

    def list_running_runs(self, *, repo_id: str, episode_id: str):
        del repo_id, episode_id
        return self._running_runs

    def add(self, run) -> None:
        self.added.append(run)

    def complete(self, **kwargs) -> None:
        self.completed.append(kwargs)


class _FakeUnitOfWork:
    """Minimal context-manager unit of work."""

    def __init__(
        self,
        *,
        event_watermark: int,
        latest_success: int | None,
        locked: bool = True,
        running_runs: tuple[KnowledgeBuildRun, ...] = (),
    ) -> None:
        self.episodes = _FakeEpisodesRepo(event_watermark=event_watermark)
        self.knowledge_build_runs = _FakeBuildRunsRepo(
            latest_success=latest_success,
            locked=locked,
            running_runs=running_runs,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


def _request(
    *, trigger: KnowledgeBuildTrigger = KnowledgeBuildTrigger.IDLE_STABLE
) -> BuildKnowledgeRequest:
    return BuildKnowledgeRequest(
        repo_id="repo-a",
        repo_root="/repo",
        episode_id="episode-1",
        trigger=trigger,
    )


def _settings() -> BuildKnowledgeSettings:
    return BuildKnowledgeSettings(
        provider="codex",
        model="gpt-5.4",
        reasoning="medium",
        timeout_seconds=180,
        max_shellbrain_reads=8,
        max_code_files=24,
        max_write_commands=20,
        idle_stable_seconds=900,
        running_run_stale_seconds=3600,
    )


def _running_run(
    *,
    run_id: str = "running-run",
    started_at: datetime,
) -> KnowledgeBuildRun:
    return KnowledgeBuildRun(
        id=run_id,
        repo_id="repo-a",
        episode_id="episode-1",
        trigger=KnowledgeBuildTrigger.IDLE_STABLE,
        status=KnowledgeBuildRunStatus.RUNNING,
        event_watermark=5,
        previous_event_watermark=None,
        provider="codex",
        model="gpt-5.4",
        reasoning="medium",
        started_at=started_at,
    )
