"""Core orchestration for immediate explicit teaching."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import json

from app.core.entities.episodes import (
    Episode,
    EpisodeEvent,
    EpisodeEventSource,
    EpisodeStatus,
)
from app.core.entities.identity import CallerIdentity
from app.core.entities.inner_agents import TeachKnowledgeSettings
from app.core.entities.knowledge_builder import (
    KnowledgeBuildRun,
    KnowledgeBuildRunStatus,
    KnowledgeBuildTrigger,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.host_apps.inner_agents import (
    BuildKnowledgeAgentResult,
    ITeachKnowledgeAgentRunner,
    TeachKnowledgeAgentRequest,
)
from app.core.ports.system.clock import IClock
from app.core.ports.system.idgen import IIdGenerator
from app.core.use_cases.knowledge_builder.teach_knowledge.request import (
    TeachKnowledgeRequest,
)
from app.core.use_cases.knowledge_builder.teach_knowledge.result import (
    TeachKnowledgeResult,
)


UowFactory = Callable[[], IUnitOfWork]


def execute_teach_knowledge(
    request: TeachKnowledgeRequest,
    *,
    uow_factory: UowFactory,
    clock: IClock,
    id_generator: IIdGenerator,
    settings: TeachKnowledgeSettings,
    agent_runner: ITeachKnowledgeAgentRunner | None,
    caller_identity: CallerIdentity | None = None,
) -> TeachKnowledgeResult:
    """Persist explicit teaching evidence and run the teach knowledge agent."""

    now = clock.now()
    episode_host_app, thread_id = _episode_identity(caller_identity)
    with uow_factory() as uow:
        uow.episodes.acquire_thread_sync_guard(
            repo_id=request.repo_id, thread_id=thread_id
        )
        episode = uow.episodes.get_or_create_episode_for_thread(
            Episode(
                id=id_generator.new_id(),
                repo_id=request.repo_id,
                host_app=episode_host_app,
                thread_id=thread_id,
                status=EpisodeStatus.ACTIVE,
                started_at=now,
                created_at=now,
            )
        )
        teaching_event_id = id_generator.new_id()
        teaching_event_seq = uow.episodes.next_event_seq(episode_id=episode.id)
        uow.episodes.append_event(
            EpisodeEvent(
                id=teaching_event_id,
                episode_id=episode.id,
                seq=teaching_event_seq,
                host_event_key=f"teach:{teaching_event_id}",
                source=EpisodeEventSource.USER,
                content=_teaching_event_content(request),
                created_at=now,
            )
        )
        previous_watermark = uow.knowledge_build_runs.latest_successful_watermark(
            repo_id=request.repo_id,
            episode_id=episode.id,
        )
        locked = uow.knowledge_build_runs.acquire_episode_lock(
            repo_id=request.repo_id,
            episode_id=episode.id,
        )
        if not locked:
            return _skipped_result(
                settings=settings,
                episode_id=episode.id,
                teaching_event_id=teaching_event_id,
                teaching_event_seq=teaching_event_seq,
                previous_event_watermark=previous_watermark,
                error_code="build_already_locked",
            )
        running_runs = uow.knowledge_build_runs.list_running_runs(
            repo_id=request.repo_id,
            episode_id=episode.id,
        )
        fresh_running_run = _fresh_running_run(
            running_runs=running_runs,
            now=now,
            stale_seconds=settings.timeout_seconds,
        )
        if fresh_running_run is not None:
            return _skipped_result(
                settings=settings,
                episode_id=episode.id,
                teaching_event_id=teaching_event_id,
                teaching_event_seq=teaching_event_seq,
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
                error_message="running teach knowledge run exceeded timeout",
                read_trace=stale_run.read_trace,
                code_trace=stale_run.code_trace,
                finished_at=now,
            )

        run_id = id_generator.new_id()
        uow.knowledge_build_runs.add(
            KnowledgeBuildRun(
                id=run_id,
                repo_id=request.repo_id,
                episode_id=episode.id,
                trigger=KnowledgeBuildTrigger.EXPLICIT_TEACH,
                status=KnowledgeBuildRunStatus.RUNNING,
                event_watermark=teaching_event_seq,
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
        episode_id=episode.id,
        teaching_event_id=teaching_event_id,
        teaching_event_seq=teaching_event_seq,
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
    return TeachKnowledgeResult(
        status=status,
        episode_id=episode.id,
        teaching_event_id=teaching_event_id,
        teaching_event_seq=teaching_event_seq,
        run_id=run_id,
        event_watermark=teaching_event_seq,
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
    request: TeachKnowledgeRequest,
    settings: TeachKnowledgeSettings,
    runner: ITeachKnowledgeAgentRunner | None,
    run_id: str,
    episode_id: str,
    teaching_event_id: str,
    teaching_event_seq: int,
) -> BuildKnowledgeAgentResult:
    """Run the concrete teach provider or return a recorded unavailable result."""

    if runner is None:
        return BuildKnowledgeAgentResult(
            status="provider_unavailable",
            provider=settings.provider,
            model=settings.model,
            reasoning=settings.reasoning,
            timeout_seconds=settings.timeout_seconds,
            error_code="missing_runner",
            error_message="no teach knowledge runner is configured",
        )
    try:
        return runner.run_teach_knowledge(
            TeachKnowledgeAgentRequest(
                run_id=run_id,
                provider=settings.provider,
                model=settings.model,
                reasoning=settings.reasoning,
                timeout_seconds=settings.timeout_seconds,
                repo_id=request.repo_id,
                repo_root=request.repo_root,
                episode_id=episode_id,
                teaching_event_id=teaching_event_id,
                teaching_event_seq=teaching_event_seq,
                teaching_text=request.text,
                current_problem=request.current_problem.model_dump(mode="python"),
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


def _episode_identity(caller_identity: CallerIdentity | None) -> tuple[str, str]:
    """Return the episode host/thread that should receive the teaching event."""

    if caller_identity is not None and caller_identity.canonical_id:
        return caller_identity.host_app, caller_identity.canonical_id
    return "shellbrain", "shellbrain:teach"


def _teaching_event_content(request: TeachKnowledgeRequest) -> str:
    """Serialize explicit teaching as deterministic episode evidence."""

    return json.dumps(
        {
            "event_type": "teaching",
            "text": request.text,
            "current_problem": request.current_problem.model_dump(mode="python"),
            "source_command": "teach",
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _skipped_result(
    *,
    settings: TeachKnowledgeSettings,
    episode_id: str,
    teaching_event_id: str,
    teaching_event_seq: int,
    previous_event_watermark: int | None,
    error_code: str,
) -> TeachKnowledgeResult:
    """Return a saved-teaching result when immediate provider work is skipped."""

    return TeachKnowledgeResult(
        status=KnowledgeBuildRunStatus.SKIPPED,
        episode_id=episode_id,
        teaching_event_id=teaching_event_id,
        teaching_event_seq=teaching_event_seq,
        run_id=None,
        event_watermark=teaching_event_seq,
        previous_event_watermark=previous_event_watermark,
        provider=settings.provider,
        model=settings.model,
        reasoning=settings.reasoning,
        error_code=error_code,
    )
