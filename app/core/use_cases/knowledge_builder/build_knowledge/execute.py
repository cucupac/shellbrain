"""Core orchestration for session-lifecycle build_knowledge runs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.core.entities.inner_agents import BuildKnowledgeSettings
from app.core.entities.knowledge_builder import (
    KnowledgeBuildRun,
    KnowledgeBuildRunStatus,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.use_cases.knowledge_builder.runs import has_running_build
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
        if has_running_build(
            uow.knowledge_build_runs,
            repo_id=request.repo_id,
            episode_id=request.episode_id,
            now=now,
            stale_seconds=settings.running_run_stale_seconds,
            error_message="running build_knowledge run exceeded stale timeout",
        ):
            return _skipped_result(
                settings=settings,
                event_watermark=event_watermark,
                previous_event_watermark=previous_watermark,
                error_code="build_already_running",
            )

        if request.baseline_only and previous_watermark is None:
            return _record_baseline_run(
                request=request,
                settings=settings,
                uow=uow,
                id_generator=id_generator,
                event_watermark=event_watermark,
                now=now,
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
    with uow_factory() as uow:
        uow.knowledge_build_runs.complete(
            run_id=run_id,
            **provider_result.model_dump(
                exclude={
                    "provider",
                    "model",
                    "reasoning",
                    "timeout_seconds",
                    "duration_ms",
                }
            ),
            finished_at=clock.now(),
        )
    return BuildKnowledgeResult(
        **provider_result.model_dump(
            exclude={
                "timeout_seconds",
                "duration_ms",
                "read_trace",
                "code_trace",
            }
        ),
        run_id=run_id,
        event_watermark=event_watermark,
        previous_event_watermark=previous_watermark,
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


def _record_baseline_run(
    *,
    request: BuildKnowledgeRequest,
    settings: BuildKnowledgeSettings,
    uow: IUnitOfWork,
    id_generator: IIdGenerator,
    event_watermark: int,
    now: datetime,
) -> BuildKnowledgeResult:
    """Persist a no-provider watermark for history that predates lifecycle builds."""

    run_id = id_generator.new_id()
    run_summary = (
        "Baselined legacy episode without invoking build_knowledge; "
        "future events after this watermark remain eligible."
    )
    uow.knowledge_build_runs.add(
        KnowledgeBuildRun(
            id=run_id,
            repo_id=request.repo_id,
            episode_id=request.episode_id,
            trigger=request.trigger,
            status=KnowledgeBuildRunStatus.SKIPPED,
            event_watermark=event_watermark,
            previous_event_watermark=None,
            provider=settings.provider,
            model=settings.model,
            reasoning=settings.reasoning,
            run_summary=run_summary,
            error_code="legacy_episode_baselined",
            started_at=now,
            finished_at=now,
            created_at=now,
        )
    )
    return BuildKnowledgeResult(
        status=KnowledgeBuildRunStatus.SKIPPED,
        run_id=run_id,
        event_watermark=event_watermark,
        previous_event_watermark=None,
        provider=settings.provider,
        model=settings.model,
        reasoning=settings.reasoning,
        write_count=0,
        skipped_item_count=0,
        run_summary=run_summary,
        error_code="legacy_episode_baselined",
    )


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
