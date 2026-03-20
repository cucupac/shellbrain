"""Helpers for assembling episode-sync telemetry rows."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.entities.telemetry import EpisodeSyncRunRecord, EpisodeSyncToolTypeRecord


def build_episode_sync_records(
    *,
    sync_run_id: str,
    source: str,
    invocation_id: str | None,
    repo_id: str,
    host_app: str,
    host_session_key: str,
    thread_id: str,
    episode_id: str | None,
    transcript_path: str | None,
    outcome: str,
    error_stage: str | None,
    error_message: str | None,
    duration_ms: int,
    imported_event_count: int,
    total_event_count: int,
    user_event_count: int,
    assistant_event_count: int,
    tool_event_count: int,
    system_event_count: int,
    tool_type_counts: dict[str, int] | None,
) -> tuple[EpisodeSyncRunRecord, list[EpisodeSyncToolTypeRecord]]:
    """Build one sync-run record plus sorted per-tool aggregate rows."""

    run = EpisodeSyncRunRecord(
        id=sync_run_id,
        source=source,
        invocation_id=invocation_id,
        repo_id=repo_id,
        host_app=host_app,
        host_session_key=host_session_key,
        thread_id=thread_id,
        episode_id=episode_id,
        transcript_path=transcript_path,
        outcome=outcome,
        error_stage=error_stage,
        error_message=error_message,
        duration_ms=duration_ms,
        imported_event_count=imported_event_count,
        total_event_count=total_event_count,
        user_event_count=user_event_count,
        assistant_event_count=assistant_event_count,
        tool_event_count=tool_event_count,
        system_event_count=system_event_count,
        created_at=datetime.now(timezone.utc),
    )
    tool_type_rows = [
        EpisodeSyncToolTypeRecord(
            sync_run_id=sync_run_id,
            tool_type=tool_type,
            event_count=count,
        )
        for tool_type, count in sorted((tool_type_counts or {}).items())
    ]
    return run, tool_type_rows
