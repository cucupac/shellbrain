"""Unit coverage for recording bounded scenario windows."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.entities.episodes import Episode, EpisodeEvent, EpisodeEventSource
from app.core.entities.memories import Memory, MemoryKind, MemoryScope
from app.core.entities.scenarios import ProblemRun, ProblemRunStatus
from app.core.entities.snapshots import (
    ShadowGitDiffResult,
    ShadowGitPathChange,
    ShadowGitPathChangeStatus,
    ShadowSnapshot,
    ShadowSnapshotReason,
    SolutionDelta,
)
from app.core.errors import DomainValidationError
from app.core.use_cases.scenarios.record import (
    ScenarioRecordRequest,
    execute_record_scenario,
)


def test_record_solved_scenario_creates_problem_run_window() -> None:
    """Solved scenarios should derive run timestamps from episode events."""

    uow = _FakeUnitOfWork()

    result = _execute_record_scenario(_solved_request(), uow)

    assert result.to_response_data() == {
        "scenario_id": "scenario-1",
        "outcome": "solved",
        "created": True,
        "solution_delta": {
            "status": "skipped",
            "solution_delta_id": None,
            "base_snapshot_id": None,
            "final_snapshot_id": None,
            "patch_sha": None,
            "changed_paths": [],
            "reason": "missing_base_snapshot",
        },
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

    result = _execute_record_scenario(_abandoned_request(), uow)

    assert result.outcome.value == "abandoned"
    run = uow.problem_runs.added[0]
    assert run.status == ProblemRunStatus.ABANDONED
    assert run.solution_memory_id is None
    assert result.solution_delta is not None
    assert result.solution_delta.reason == "outcome_not_solved"


def test_record_solved_scenario_creates_solution_delta_when_snapshots_exist() -> None:
    """Solved scenarios should attach exact patch identity when snapshots bound the window."""

    uow = _FakeUnitOfWork(
        snapshots=[
            _snapshot(
                snapshot_id="snap-base",
                commit_sha="commit-base",
                reason=ShadowSnapshotReason.BASELINE,
                event_seq=1,
            ),
            _snapshot(
                snapshot_id="snap-final",
                commit_sha="commit-final",
                reason=ShadowSnapshotReason.CLOSEOUT,
                event_seq=2,
                changed_paths=("app/example.py",),
            ),
        ]
    )

    result = _execute_record_scenario(_solved_request(), uow)

    assert result.solution_delta is not None
    assert result.solution_delta.to_response_data() == {
        "status": "created",
        "solution_delta_id": "delta-1",
        "base_snapshot_id": "snap-base",
        "final_snapshot_id": "snap-final",
        "patch_sha": "patch-sha",
        "changed_paths": ["app/example.py"],
        "reason": None,
    }
    assert len(uow.snapshots.solution_deltas) == 1
    assert uow.snapshots.solution_deltas[0].problem_run_id == "scenario-1"


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

    result = _execute_record_scenario(_solved_request(), uow)

    assert result.to_response_data() == {
        "scenario_id": "scenario-existing",
        "outcome": "solved",
        "created": False,
        "solution_delta": {
            "status": "skipped",
            "solution_delta_id": None,
            "base_snapshot_id": None,
            "final_snapshot_id": None,
            "patch_sha": None,
            "changed_paths": [],
            "reason": "existing_problem_run_has_no_solution_delta",
        },
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
        _execute_record_scenario(_solved_request(), uow)

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
        _execute_record_scenario(_solved_request(), uow)

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
    def __init__(self) -> None:
        self._ids = iter(("scenario-1", "delta-1", "delta-2"))

    def new_id(self) -> str:
        return next(self._ids)


class _FakeUnitOfWork:
    def __init__(
        self,
        *,
        existing: ProblemRun | None = None,
        opened_seq: int = 1,
        closed_seq: int = 2,
        problem_repo_id: str = "repo-a",
        solution_kind: MemoryKind = MemoryKind.SOLUTION,
        snapshots: list[ShadowSnapshot] | None = None,
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
        self.snapshots = _FakeSnapshotsRepo(snapshots=snapshots or [])


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


class _FakeSnapshotsRepo:
    def __init__(self, *, snapshots: list[ShadowSnapshot]) -> None:
        self._snapshots = snapshots
        self.solution_deltas: list[SolutionDelta] = []

    def latest_snapshot(self, **kwargs) -> ShadowSnapshot | None:
        del kwargs
        return self._snapshots[-1] if self._snapshots else None

    def latest_snapshot_at_or_before_event(
        self, *, event_seq: int, **kwargs
    ) -> ShadowSnapshot | None:
        del kwargs
        candidates = [
            snapshot
            for snapshot in self._snapshots
            if snapshot.captured_after_event_seq is None
            or snapshot.captured_after_event_seq <= event_seq
        ]
        return candidates[-1] if candidates else None

    def latest_snapshot_in_event_window(
        self, *, opened_event_seq: int, closed_event_seq: int, **kwargs
    ) -> ShadowSnapshot | None:
        del kwargs
        candidates = [
            snapshot
            for snapshot in self._snapshots
            if snapshot.reason is not ShadowSnapshotReason.BASELINE_ONLY
            and snapshot.captured_after_event_seq is not None
            and opened_event_seq <= snapshot.captured_after_event_seq <= closed_event_seq
        ]
        return candidates[-1] if candidates else None

    def get_solution_delta_for_problem_run(
        self, *, problem_run_id: str
    ) -> SolutionDelta | None:
        for delta in self.solution_deltas:
            if delta.problem_run_id == problem_run_id:
                return delta
        return None

    def add_snapshot(self, snapshot: ShadowSnapshot) -> None:
        self._snapshots.append(snapshot)

    def add_solution_delta(self, delta: SolutionDelta) -> None:
        self.solution_deltas.append(delta)


class _FakeShadowGitStore:
    def diff_snapshot_pair(self, **kwargs) -> ShadowGitDiffResult:
        assert kwargs["base_commit_sha"] == "commit-base"
        assert kwargs["final_commit_sha"] == "commit-final"
        return ShadowGitDiffResult(
            patch_sha="patch-sha",
            path_changes=(
                ShadowGitPathChange(
                    status=ShadowGitPathChangeStatus.MODIFIED,
                    path="app/example.py",
                ),
            ),
        )

    def capture_snapshot(self, request):  # pragma: no cover - scenario tests do not capture
        raise AssertionError("scenario record should not capture snapshots")


def _execute_record_scenario(request: ScenarioRecordRequest, uow: _FakeUnitOfWork):
    return execute_record_scenario(
        request,
        uow,
        repo_root="/repo",
        id_generator=_IdGen(),
        shadow_git_store=_FakeShadowGitStore(),
    )


def _snapshot(
    *,
    snapshot_id: str,
    commit_sha: str,
    reason: ShadowSnapshotReason,
    event_seq: int | None,
    changed_paths: tuple[str, ...] = (),
) -> ShadowSnapshot:
    return ShadowSnapshot(
        id=snapshot_id,
        repo_id="repo-a",
        repo_root="/repo",
        episode_id="episode-1",
        captured_after_event_seq=event_seq,
        shadow_commit_sha=commit_sha,
        parent_shadow_commit_sha=None,
        changed_paths=changed_paths,
        reason=reason,
        created_at=_dt(event_seq or 0),
    )
