"""Core orchestration for recording bounded problem-solving scenarios."""

from __future__ import annotations

from app.core.entities.episodes import Episode, EpisodeEvent
from app.core.entities.memories import Memory, MemoryKind
from app.core.entities.scenarios import (
    ProblemRun,
    outcome_to_problem_run_status,
)
from app.core.errors import DomainValidationError, ErrorCode, ErrorDetail
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.system.idgen import IIdGenerator
from app.core.use_cases.scenarios.record.request import ScenarioRecordRequest
from app.core.use_cases.scenarios.record.result import ScenarioRecordResult


_BUILD_KNOWLEDGE_ACTOR = "build_knowledge"


def execute_record_scenario(
    request: ScenarioRecordRequest,
    uow: IUnitOfWork,
    *,
    id_generator: IIdGenerator,
) -> ScenarioRecordResult:
    """Validate references and persist one scenario run window."""

    episode, opened_event, closed_event, problem_memory, solution_memory, errors = (
        _load_references(request, uow)
    )
    if errors:
        raise DomainValidationError(errors)
    assert episode is not None
    assert opened_event is not None
    assert closed_event is not None
    assert problem_memory is not None

    scenario = request.scenario
    existing = uow.problem_runs.get_by_scenario_key(
        repo_id=request.repo_id,
        episode_id=scenario.episode_id,
        problem_memory_id=scenario.problem_memory_id,
        opened_event_id=scenario.opened_event_id,
    )
    status = outcome_to_problem_run_status(scenario.outcome)
    if existing is not None:
        if _matches_existing_scenario(
            existing=existing,
            status=status.value,
            closed_event_id=scenario.closed_event_id,
            solution_memory_id=scenario.solution_memory_id,
        ):
            return ScenarioRecordResult(
                scenario_id=existing.id,
                outcome=scenario.outcome,
                created=False,
            )
        raise DomainValidationError(
            [
                ErrorDetail(
                    code=ErrorCode.CONFLICT,
                    message="Scenario key already exists with different terminal details",
                    field="scenario",
                )
            ]
        )

    run = ProblemRun(
        id=id_generator.new_id(),
        repo_id=request.repo_id,
        thread_id=episode.thread_id,
        host_app=episode.host_app,
        host_session_key=None,
        episode_id=episode.id,
        opened_event_id=opened_event.id,
        status=status,
        opened_at=opened_event.created_at,
        closed_at=closed_event.created_at,
        opened_by=_BUILD_KNOWLEDGE_ACTOR,
        closed_by=_BUILD_KNOWLEDGE_ACTOR,
        closed_event_id=closed_event.id,
        problem_memory_id=problem_memory.id,
        solution_memory_id=solution_memory.id if solution_memory else None,
    )
    uow.problem_runs.add(run)
    return ScenarioRecordResult(
        scenario_id=run.id,
        outcome=scenario.outcome,
        created=True,
    )


def _load_references(
    request: ScenarioRecordRequest,
    uow: IUnitOfWork,
) -> tuple[
    Episode | None,
    EpisodeEvent | None,
    EpisodeEvent | None,
    Memory | None,
    Memory | None,
    list[ErrorDetail],
]:
    """Load scenario references and collect all deterministic validation errors."""

    scenario = request.scenario
    errors: list[ErrorDetail] = []
    episode = uow.episodes.get_episode(
        repo_id=request.repo_id, episode_id=scenario.episode_id
    )
    if episode is None:
        errors.append(
            ErrorDetail(
                code=ErrorCode.NOT_FOUND,
                message=f"Episode not found: {scenario.episode_id}",
                field="scenario.episode_id",
            )
        )

    opened_event = uow.episodes.get_event(
        repo_id=request.repo_id,
        episode_id=scenario.episode_id,
        event_id=scenario.opened_event_id,
    )
    closed_event = uow.episodes.get_event(
        repo_id=request.repo_id,
        episode_id=scenario.episode_id,
        event_id=scenario.closed_event_id,
    )
    if opened_event is None:
        errors.append(
            ErrorDetail(
                code=ErrorCode.NOT_FOUND,
                message=f"Episode event not found: {scenario.opened_event_id}",
                field="scenario.opened_event_id",
            )
        )
    if closed_event is None:
        errors.append(
            ErrorDetail(
                code=ErrorCode.NOT_FOUND,
                message=f"Episode event not found: {scenario.closed_event_id}",
                field="scenario.closed_event_id",
            )
        )
    if opened_event and closed_event and closed_event.seq <= opened_event.seq:
        errors.append(
            ErrorDetail(
                code=ErrorCode.SEMANTIC_ERROR,
                message="closed_event_id must refer to an event after opened_event_id",
                field="scenario.closed_event_id",
            )
        )
    if opened_event and opened_event.created_at is None:
        errors.append(
            ErrorDetail(
                code=ErrorCode.INTEGRITY_ERROR,
                message="opened_event_id has no created_at timestamp",
                field="scenario.opened_event_id",
            )
        )
    if closed_event and closed_event.created_at is None:
        errors.append(
            ErrorDetail(
                code=ErrorCode.INTEGRITY_ERROR,
                message="closed_event_id has no created_at timestamp",
                field="scenario.closed_event_id",
            )
        )

    problem_memory = uow.memories.get(scenario.problem_memory_id)
    errors.extend(
        _validate_memory(
            memory=problem_memory,
            memory_id=scenario.problem_memory_id,
            repo_id=request.repo_id,
            expected_kind=MemoryKind.PROBLEM,
            field="scenario.problem_memory_id",
        )
    )
    solution_memory = None
    if scenario.solution_memory_id is not None:
        solution_memory = uow.memories.get(scenario.solution_memory_id)
        errors.extend(
            _validate_memory(
                memory=solution_memory,
                memory_id=scenario.solution_memory_id,
                repo_id=request.repo_id,
                expected_kind=MemoryKind.SOLUTION,
                field="scenario.solution_memory_id",
            )
        )
    return episode, opened_event, closed_event, problem_memory, solution_memory, errors


def _validate_memory(
    *,
    memory: Memory | None,
    memory_id: str,
    repo_id: str,
    expected_kind: MemoryKind,
    field: str,
) -> list[ErrorDetail]:
    """Validate an exact repo memory reference."""

    if memory is None:
        return [
            ErrorDetail(
                code=ErrorCode.NOT_FOUND,
                message=f"Memory not found: {memory_id}",
                field=field,
            )
        ]
    errors: list[ErrorDetail] = []
    if memory.repo_id != repo_id:
        errors.append(
            ErrorDetail(
                code=ErrorCode.INTEGRITY_ERROR,
                message="Scenario memories must belong to this repo_id",
                field=field,
            )
        )
    if memory.kind != expected_kind:
        errors.append(
            ErrorDetail(
                code=ErrorCode.INTEGRITY_ERROR,
                message=f"{field} must reference a {expected_kind.value} memory",
                field=field,
            )
        )
    return errors


def _matches_existing_scenario(
    *,
    existing: ProblemRun,
    status: str,
    closed_event_id: str,
    solution_memory_id: str | None,
) -> bool:
    """Return whether an existing row is an idempotent replay."""

    return (
        existing.status.value == status
        and existing.closed_event_id == closed_event_id
        and existing.solution_memory_id == solution_memory_id
    )
