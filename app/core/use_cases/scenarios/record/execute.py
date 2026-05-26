"""Core orchestration for recording bounded problem-solving scenarios."""

from __future__ import annotations

from app.core.entities.episodes import Episode, EpisodeEvent
from app.core.entities.memories import Memory, MemoryKind
from app.core.entities.scenarios import (
    ProblemRun,
    ScenarioOutcome,
    outcome_to_problem_run_status,
)
from app.core.entities.snapshots import (
    AvailableCodeDeltaContext,
    SolutionDelta,
    UnavailableCodeDeltaContext,
)
from app.core.errors import DomainValidationError, ErrorCode, ErrorDetail
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.local_state.shadow_git import IShadowGitStore
from app.core.ports.system.idgen import IIdGenerator
from app.core.use_cases.scenarios.record.request import ScenarioRecordRequest
from app.core.use_cases.scenarios.record.result import (
    ScenarioRecordResult,
    SolutionDeltaRecordResult,
)
from app.core.use_cases.snapshots.code_delta_context import (
    build_code_delta_context_from_snapshots,
)


_BUILD_KNOWLEDGE_ACTOR = "build_knowledge"


def execute_record_scenario(
    request: ScenarioRecordRequest,
    uow: IUnitOfWork,
    *,
    repo_root: str,
    id_generator: IIdGenerator,
    shadow_git_store: IShadowGitStore,
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
                solution_delta=_existing_solution_delta_result(existing.id, uow),
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
    solution_delta_result = _attach_solution_delta(
        request=request,
        run=run,
        repo_root=repo_root,
        opened_event=opened_event,
        closed_event=closed_event,
        uow=uow,
        id_generator=id_generator,
        shadow_git_store=shadow_git_store,
    )
    return ScenarioRecordResult(
        scenario_id=run.id,
        outcome=scenario.outcome,
        created=True,
        solution_delta=solution_delta_result,
    )


def _existing_solution_delta_result(
    problem_run_id: str, uow: IUnitOfWork
) -> SolutionDeltaRecordResult:
    """Return replay metadata for a previously attached solution delta."""

    existing_delta = uow.snapshots.get_solution_delta_for_problem_run(
        problem_run_id=problem_run_id
    )
    if existing_delta is None:
        return SolutionDeltaRecordResult(
            status="skipped", reason="existing_problem_run_has_no_solution_delta"
        )
    return SolutionDeltaRecordResult(
        status="exists",
        solution_delta_id=existing_delta.id,
        base_snapshot_id=existing_delta.base_snapshot_id,
        final_snapshot_id=existing_delta.final_snapshot_id,
        patch_sha=existing_delta.patch_sha,
        changed_paths=existing_delta.changed_paths,
    )


def _attach_solution_delta(
    *,
    request: ScenarioRecordRequest,
    run: ProblemRun,
    repo_root: str,
    opened_event: EpisodeEvent,
    closed_event: EpisodeEvent,
    uow: IUnitOfWork,
    id_generator: IIdGenerator,
    shadow_git_store: IShadowGitStore,
) -> SolutionDeltaRecordResult:
    """Attach a patch-backed delta when a solved run has valid snapshots."""

    if request.scenario.outcome is not ScenarioOutcome.SOLVED:
        return SolutionDeltaRecordResult(status="skipped", reason="outcome_not_solved")

    base_snapshot = uow.snapshots.latest_snapshot_at_or_before_event(
        repo_id=request.repo_id,
        repo_root=repo_root,
        episode_id=request.scenario.episode_id,
        event_seq=opened_event.seq,
    )
    if base_snapshot is None:
        return SolutionDeltaRecordResult(status="skipped", reason="missing_base_snapshot")
    final_snapshot = uow.snapshots.latest_snapshot_in_event_window(
        repo_id=request.repo_id,
        repo_root=repo_root,
        episode_id=request.scenario.episode_id,
        opened_event_seq=opened_event.seq,
        closed_event_seq=closed_event.seq,
    )
    if final_snapshot is None:
        return SolutionDeltaRecordResult(
            status="skipped", reason="missing_final_snapshot"
        )
    code_delta_context = build_code_delta_context_from_snapshots(
        repo_root=repo_root,
        base_snapshot=base_snapshot,
        final_snapshot=final_snapshot,
        baseline_only_base_event_seq=opened_event.seq - 1,
        shadow_git_store=shadow_git_store,
    )
    if isinstance(code_delta_context, UnavailableCodeDeltaContext):
        return SolutionDeltaRecordResult(
            status="skipped", reason=code_delta_context.reason.value
        )
    assert isinstance(code_delta_context, AvailableCodeDeltaContext)
    delta = SolutionDelta(
        id=id_generator.new_id(),
        problem_run_id=run.id,
        repo_id=request.repo_id,
        repo_root=repo_root,
        episode_id=request.scenario.episode_id,
        base_snapshot_id=code_delta_context.base_snapshot_id,
        final_snapshot_id=code_delta_context.final_snapshot_id,
        patch_sha=code_delta_context.patch_sha,
        changed_paths=code_delta_context.changed_paths,
    )
    uow.snapshots.add_solution_delta(delta)
    return SolutionDeltaRecordResult(
        status="created",
        solution_delta_id=delta.id,
        base_snapshot_id=delta.base_snapshot_id,
        final_snapshot_id=delta.final_snapshot_id,
        patch_sha=delta.patch_sha,
        changed_paths=delta.changed_paths,
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
