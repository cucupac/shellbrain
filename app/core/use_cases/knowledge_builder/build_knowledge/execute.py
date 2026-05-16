"""Core orchestration for session-lifecycle build_knowledge runs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from app.core.entities.inner_agents import BuildKnowledgeSettings
from app.core.entities.knowledge_builder import (
    KnowledgeBuildRun,
    KnowledgeBuildRunStatus,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.host_apps.inner_agents import (
    BuildKnowledgeAgentRequest,
    BuildKnowledgeAgentResult,
    IBuildKnowledgeAgentRunner,
)
from app.core.ports.system.clock import IClock
from app.core.ports.system.idgen import IIdGenerator
from app.core.use_cases.knowledge_builder.build_knowledge.request import (
    BuildKnowledgeRequest,
)
from app.core.use_cases.knowledge_builder.build_knowledge.result import (
    BuildKnowledgeResult,
)


UowFactory = Callable[[], IUnitOfWork]


def execute_build_knowledge(
    request: BuildKnowledgeRequest,
    *,
    uow_factory: UowFactory,
    clock: IClock,
    id_generator: IIdGenerator,
    settings: BuildKnowledgeSettings,
    agent_runner: IBuildKnowledgeAgentRunner | None,
) -> BuildKnowledgeResult:
    """Run build_knowledge when an episode has unprocessed event evidence."""

    now = clock.now()
    with uow_factory() as uow:
        locked = uow.knowledge_build_runs.acquire_episode_lock(
            repo_id=request.repo_id,
            episode_id=request.episode_id,
        )
        if not locked:
            return _skipped_result(
                settings=settings,
                event_watermark=0,
                previous_event_watermark=None,
                error_code="build_already_locked",
            )
        episode = uow.episodes.get_episode(
            repo_id=request.repo_id,
            episode_id=request.episode_id,
        )
        if episode is None:
            return _skipped_result(
                settings=settings,
                event_watermark=0,
                previous_event_watermark=None,
                error_code="episode_not_found",
            )
        event_watermark = uow.episodes.event_watermark(
            repo_id=request.repo_id,
            episode_id=request.episode_id,
        )
        previous_watermark = uow.knowledge_build_runs.latest_successful_watermark(
            repo_id=request.repo_id,
            episode_id=request.episode_id,
        )
        if event_watermark <= (previous_watermark or 0):
            return _skipped_result(
                settings=settings,
                event_watermark=event_watermark,
                previous_event_watermark=previous_watermark,
                error_code="no_new_events",
            )
        running_runs = uow.knowledge_build_runs.list_running_runs(
            repo_id=request.repo_id,
            episode_id=request.episode_id,
        )
        fresh_running_run = _fresh_running_run(
            running_runs=running_runs,
            now=now,
            stale_seconds=settings.running_run_stale_seconds,
        )
        if fresh_running_run is not None:
            return _skipped_result(
                settings=settings,
                event_watermark=event_watermark,
                previous_event_watermark=previous_watermark,
                error_code="build_already_running",
            )
        for stale_run in running_runs:
            uow.knowledge_build_runs.complete(
                run_id=stale_run.id,
                status=KnowledgeBuildRunStatus.TIMEOUT,
                write_count=stale_run.write_count,
                skipped_item_count=stale_run.skipped_item_count,
                input_tokens=stale_run.input_tokens,
                output_tokens=stale_run.output_tokens,
                reasoning_output_tokens=stale_run.reasoning_output_tokens,
                cached_input_tokens_total=stale_run.cached_input_tokens_total,
                cache_read_input_tokens=stale_run.cache_read_input_tokens,
                cache_creation_input_tokens=stale_run.cache_creation_input_tokens,
                capture_quality=stale_run.capture_quality,
                run_summary=stale_run.run_summary,
                error_code="stale_running_run",
                error_message="running build_knowledge run exceeded stale timeout",
                read_trace=stale_run.read_trace,
                code_trace=stale_run.code_trace,
                finished_at=now,
            )

        run_id = id_generator.new_id()
        uow.knowledge_build_runs.add(
            KnowledgeBuildRun(
                id=run_id,
                repo_id=request.repo_id,
                episode_id=request.episode_id,
                trigger=request.trigger,
                status=KnowledgeBuildRunStatus.RUNNING,
                event_watermark=event_watermark,
                previous_event_watermark=previous_watermark,
                provider=settings.provider,
                model=settings.model,
                reasoning=settings.reasoning,
                started_at=now,
                created_at=now,
            )
        )

    provider_result = _run_provider(
        request=request,
        settings=settings,
        runner=agent_runner,
        run_id=run_id,
        event_watermark=event_watermark,
        previous_watermark=previous_watermark,
    )
    status = _run_status(provider_result.status)
    with uow_factory() as uow:
        uow.knowledge_build_runs.complete(
            run_id=run_id,
            status=status,
            write_count=provider_result.write_count,
            skipped_item_count=provider_result.skipped_item_count,
            input_tokens=provider_result.input_tokens,
            output_tokens=provider_result.output_tokens,
            reasoning_output_tokens=provider_result.reasoning_output_tokens,
            cached_input_tokens_total=provider_result.cached_input_tokens_total,
            cache_read_input_tokens=provider_result.cache_read_input_tokens,
            cache_creation_input_tokens=provider_result.cache_creation_input_tokens,
            capture_quality=provider_result.capture_quality,
            run_summary=provider_result.run_summary,
            error_code=provider_result.error_code,
            error_message=provider_result.error_message,
            read_trace=provider_result.read_trace,
            code_trace=provider_result.code_trace,
            finished_at=clock.now(),
        )
    return BuildKnowledgeResult(
        status=status,
        run_id=run_id,
        event_watermark=event_watermark,
        previous_event_watermark=previous_watermark,
        provider=provider_result.provider,
        model=provider_result.model,
        reasoning=provider_result.reasoning,
        write_count=provider_result.write_count,
        skipped_item_count=provider_result.skipped_item_count,
        input_tokens=provider_result.input_tokens,
        output_tokens=provider_result.output_tokens,
        reasoning_output_tokens=provider_result.reasoning_output_tokens,
        cached_input_tokens_total=provider_result.cached_input_tokens_total,
        cache_read_input_tokens=provider_result.cache_read_input_tokens,
        cache_creation_input_tokens=provider_result.cache_creation_input_tokens,
        capture_quality=provider_result.capture_quality,
        run_summary=provider_result.run_summary,
        error_code=provider_result.error_code,
        error_message=provider_result.error_message,
    )


def _run_provider(
    *,
    request: BuildKnowledgeRequest,
    settings: BuildKnowledgeSettings,
    runner: IBuildKnowledgeAgentRunner | None,
    run_id: str,
    event_watermark: int,
    previous_watermark: int | None,
) -> BuildKnowledgeAgentResult:
    """Run the concrete provider or return a recorded unavailable result."""

    if runner is None:
        return BuildKnowledgeAgentResult(
            status="provider_unavailable",
            provider=settings.provider,
            model=settings.model,
            reasoning=settings.reasoning,
            timeout_seconds=settings.timeout_seconds,
            error_code="missing_runner",
            error_message="no build_knowledge runner is configured",
        )
    try:
        return runner.run_build_knowledge(
            BuildKnowledgeAgentRequest(
                run_id=run_id,
                provider=settings.provider,
                model=settings.model,
                reasoning=settings.reasoning,
                timeout_seconds=settings.timeout_seconds,
                repo_id=request.repo_id,
                repo_root=request.repo_root,
                episode_id=request.episode_id,
                trigger=request.trigger.value,
                event_watermark=event_watermark,
                previous_event_watermark=previous_watermark,
                max_shellbrain_reads=settings.max_shellbrain_reads,
                max_code_files=settings.max_code_files,
                max_write_commands=settings.max_write_commands,
            )
        )
    except Exception as exc:  # pragma: no cover - defensive core boundary
        return BuildKnowledgeAgentResult(
            status="error",
            provider=settings.provider,
            model=settings.model,
            reasoning=settings.reasoning,
            timeout_seconds=settings.timeout_seconds,
            error_code="runner_exception",
            error_message=str(exc),
        )


def _run_status(value: object) -> KnowledgeBuildRunStatus:
    """Coerce provider status into the durable run status enum."""

    if isinstance(value, KnowledgeBuildRunStatus):
        return value
    return KnowledgeBuildRunStatus(str(value))


def _fresh_running_run(
    *,
    running_runs: tuple[KnowledgeBuildRun, ...],
    now: datetime,
    stale_seconds: int,
) -> KnowledgeBuildRun | None:
    """Return a fresh running row when any active run is still inside its lease."""

    stale_before = now - timedelta(seconds=stale_seconds)
    for run in running_runs:
        if run.started_at is None or run.started_at > stale_before:
            return run
    return None


def _skipped_result(
    *,
    settings: BuildKnowledgeSettings,
    event_watermark: int,
    previous_event_watermark: int | None,
    error_code: str,
) -> BuildKnowledgeResult:
    """Return a no-run skipped result."""

    return BuildKnowledgeResult(
        status=KnowledgeBuildRunStatus.SKIPPED,
        run_id=None,
        event_watermark=event_watermark,
        previous_event_watermark=previous_event_watermark,
        provider=settings.provider,
        model=settings.model,
        reasoning=settings.reasoning,
        error_code=error_code,
    )
