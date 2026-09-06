"""Shared lease handling for teaching and session consolidation."""

from datetime import datetime, timedelta

from app.core.entities.knowledge_builder import KnowledgeBuildRunStatus
from app.core.ports.db.knowledge_builder import IKnowledgeBuildRunsRepo


def has_running_build(
    repo: IKnowledgeBuildRunsRepo,
    *,
    repo_id: str,
    episode_id: str,
    now: datetime,
    stale_seconds: int,
    error_message: str,
) -> bool:
    """Keep fresh runs and finalize expired runs under the caller's episode lock."""

    running_runs = repo.list_running_runs(repo_id=repo_id, episode_id=episode_id)
    stale_before = now - timedelta(seconds=stale_seconds)
    if any(
        run.started_at is None or run.started_at > stale_before for run in running_runs
    ):
        return True
    for stale_run in running_runs:
        repo.complete(
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
            error_message=error_message,
            read_trace=stale_run.read_trace,
            code_trace=stale_run.code_trace,
            finished_at=now,
        )
    return False
