"""Unit coverage for recording bounded scenario windows."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.entities.episodes import Episode, EpisodeEvent, EpisodeEventSource
from app.core.entities.memories import Memory, MemoryKind, MemoryScope
from app.core.entities.scenarios import ProblemRun, ProblemRunStatus
from app.core.errors import DomainValidationError
from app.core.use_cases.scenarios.record import (
    ScenarioRecordRequest,
    execute_record_scenario,
)


def test_record_solved_scenario_creates_problem_run_window() -> None:
    """Solved scenarios should derive run timestamps from episode events."""

    uow = _FakeUnitOfWork()

    result = execute_record_scenario(_solved_request(), uow, id_generator=_IdGen())

    assert result.to_response_data() == {
        "scenario_id": "scenario-1",
        "outcome": "solved",
        "created": True,
    }
    assert len(uow.problem_runs.added) == 1
    run = uow.problem_runs.added[0]
    assert run.status == ProblemRunStatus.CLOSED
    assert run.opened_by == "build_knowledge"
    assert run.closed_by == "build_knowledge"
    assert run.opened_at == uow.opened.created_at
    assert run.closed_at == uow.closed.created_at
    assert run.problem_memory_id == "mem-problem"
    assert run.solution_memory_id == "mem-solution"
    assert run.thread_id == "codex:thread-1"
    assert run.host_app == "codex"


def test_record_abandoned_scenario_omits_solution_memory() -> None:
    """Abandoned scenarios should map to the abandoned problem-run status."""

    uow = _FakeUnitOfWork()

    result = execute_record_scenario(_abandoned_request(), uow, id_generator=_IdGen())

    assert result.outcome.value == "abandoned"
    run = uow.problem_runs.added[0]
    assert run.status == ProblemRunStatus.ABANDONED
    assert run.solution_memory_id is None


def test_record_scenario_replay_is_idempotent_when_terminal_details_match() -> None:
    """Repeating the same scenario should return the existing row."""

    existing = ProblemRun(
        id="scenario-existing",
        repo_id="repo-a",
        status=ProblemRunStatus.CLOSED,
        opened_at=_dt(1),
        closed_at=_dt(2),
        opened_by="build_knowledge",
        closed_by="build_knowledge",
        episode_id="episode-1",
        opened_event_id="evt-open",
        closed_event_id="evt-close",
        problem_memory_id="mem-problem",
        solution_memory_id="mem-solution",
    )
    uow = _FakeUnitOfWork(existing=existing)

    result = execute_record_scenario(_solved_request(), uow, id_generator=_IdGen())

    assert result.to_response_data() == {
        "scenario_id": "scenario-existing",
        "outcome": "solved",
        "created": False,
    }
    assert uow.problem_runs.added == []


def test_record_scenario_rejects_conflicting_replay() -> None:
    """The natural key should not silently mutate terminal details."""

    existing = ProblemRun(
        id="scenario-existing",
        repo_id="repo-a",
        status=ProblemRunStatus.ABANDONED,
        opened_at=_dt(1),
        closed_at=_dt(2),
        opened_by="build_knowledge",
        closed_by="build_knowledge",
        episode_id="episode-1",
        opened_event_id="evt-open",
        closed_event_id="evt-close",
        problem_memory_id="mem-problem",
        solution_memory_id=None,
    )
    uow = _FakeUnitOfWork(existing=existing)

    with pytest.raises(DomainValidationError) as excinfo:
        execute_record_scenario(_solved_request(), uow, id_generator=_IdGen())

    assert excinfo.value.errors[0].code.value == "conflict"
    assert uow.problem_runs.added == []


def test_record_scenario_requires_event_order_and_exact_repo_memories() -> None:
    """Scenario references should be repo-exact and ordered."""

    uow = _FakeUnitOfWork(
        opened_seq=4,
        closed_seq=3,
        problem_repo_id="other-repo",
        solution_kind=MemoryKind.FACT,
    )

    with pytest.raises(DomainValidationError) as excinfo:
        execute_record_scenario(_solved_request(), uow, id_generator=_IdGen())

    messages = [error.message for error in excinfo.value.errors]
    assert "closed_event_id must refer to an event after opened_event_id" in messages
    assert "Scenario memories must belong to this repo_id" in messages
    assert "scenario.solution_memory_id must reference a solution memory" in messages


def _solved_request() -> ScenarioRecordRequest:
    return ScenarioRecordRequest.model_validate(
        {
            "schema_version": "scenario.v1",
            "repo_id": "repo-a",
            "scenario": {
                "episode_id": "episode-1",
                "outcome": "solved",
                "problem_memory_id": "mem-problem",
                "solution_memory_id": "mem-solution",
                "opened_event_id": "evt-open",
                "closed_event_id": "evt-close",
            },
        }
    )


def _abandoned_request() -> ScenarioRecordRequest:
    return ScenarioRecordRequest.model_validate(
        {
            "schema_version": "scenario.v1",
            "repo_id": "repo-a",
            "scenario": {
                "episode_id": "episode-1",
                "outcome": "abandoned",
                "problem_memory_id": "mem-problem",
                "opened_event_id": "evt-open",
                "closed_event_id": "evt-close",
            },
        }
    )


def _dt(minute: int) -> datetime:
    return datetime(2026, 5, 15, 12, minute, tzinfo=timezone.utc)


class _IdGen:
    def new_id(self) -> str:
        return "scenario-1"


class _FakeUnitOfWork:
    def __init__(
        self,
        *,
        existing: ProblemRun | None = None,
        opened_seq: int = 1,
        closed_seq: int = 2,
        problem_repo_id: str = "repo-a",
        solution_kind: MemoryKind = MemoryKind.SOLUTION,
    ) -> None:
        self.opened = EpisodeEvent(
            id="evt-open",
            episode_id="episode-1",
            seq=opened_seq,
            host_event_key="open",
            source=EpisodeEventSource.USER,
            content="problem appears",
            created_at=_dt(1),
        )
        self.closed = EpisodeEvent(
            id="evt-close",
            episode_id="episode-1",
            seq=closed_seq,
            host_event_key="close",
            source=EpisodeEventSource.ASSISTANT,
            content="solution found",
            created_at=_dt(2),
        )
        self.episodes = _FakeEpisodesRepo(opened=self.opened, closed=self.closed)
        self.memories = _FakeMemoriesRepo(
            {
                "mem-problem": Memory(
                    id="mem-problem",
                    repo_id=problem_repo_id,
                    scope=MemoryScope.REPO,
                    kind=MemoryKind.PROBLEM,
                    text="problem",
                ),
                "mem-solution": Memory(
                    id="mem-solution",
                    repo_id="repo-a",
                    scope=MemoryScope.REPO,
                    kind=solution_kind,
                    text="solution",
                ),
            }
        )
        self.problem_runs = _FakeProblemRunsRepo(existing=existing)


class _FakeEpisodesRepo:
    def __init__(self, *, opened: EpisodeEvent, closed: EpisodeEvent) -> None:
        self._events = {opened.id: opened, closed.id: closed}

    def get_episode(self, *, repo_id: str, episode_id: str) -> Episode | None:
        if repo_id != "repo-a" or episode_id != "episode-1":
            return None
        return Episode(
            id="episode-1",
            repo_id="repo-a",
            host_app="codex",
            thread_id="codex:thread-1",
        )

    def get_event(
        self, *, repo_id: str, episode_id: str, event_id: str
    ) -> EpisodeEvent | None:
        if repo_id != "repo-a" or episode_id != "episode-1":
            return None
        return self._events.get(event_id)


class _FakeMemoriesRepo:
    def __init__(self, memories: dict[str, Memory]) -> None:
        self._memories = memories

    def get(self, memory_id: str) -> Memory | None:
        return self._memories.get(memory_id)


class _FakeProblemRunsRepo:
    def __init__(self, *, existing: ProblemRun | None) -> None:
        self._existing = existing
        self.added: list[ProblemRun] = []

    def get_by_scenario_key(self, **kwargs) -> ProblemRun | None:
        del kwargs
        return self._existing

    def add(self, run: ProblemRun) -> None:
        self.added.append(run)
