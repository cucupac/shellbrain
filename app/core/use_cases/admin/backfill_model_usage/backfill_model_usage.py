"""Backfill model usage from Shellbrain-linked host transcript sessions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path

from app.core.use_cases.admin.backfill_model_usage.request import (
    BackfillModelUsageRequest,
    LinkedModelUsageSession,
)
from app.core.use_cases.admin.backfill_model_usage.result import BackfillSummary


def backfill_model_usage(
    request: BackfillModelUsageRequest,
    *,
    collect_model_usage_records_for_session: Callable[..., Sequence[object]],
    persist_model_usage_records: Callable[[Sequence[object]], None],
) -> BackfillSummary:
    """Backfill normalized model usage for linked historical sessions."""

    host_counts: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    sessions_with_records = 0
    sessions_skipped = 0
    sessions_failed = 0
    records_attempted = 0

    for session in request.sessions:
        try:
            records = collect_model_usage_records_for_session(
                repo_id=session.repo_id,
                host_app=session.host_app,
                host_session_key=session.host_session_key,
                thread_id=session.thread_id,
                episode_id=session.episode_id,
                transcript_path=Path(session.transcript_path),
            )
        except Exception as exc:
            sessions_failed += 1
            errors.append(
                {
                    "host_app": session.host_app,
                    "host_session_key": session.host_session_key,
                    "message": str(exc),
                }
            )
            continue

        if not records:
            sessions_skipped += 1
            continue
        persist_model_usage_records(records)
        sessions_with_records += 1
        records_attempted += len(records)
        host_counts[session.host_app] += len(records)

    return BackfillSummary(
        sessions_examined=len(request.sessions),
        sessions_with_records=sessions_with_records,
        sessions_skipped=sessions_skipped,
        sessions_failed=sessions_failed,
        records_attempted=records_attempted,
        host_counts=dict(sorted(host_counts.items())),
        errors=errors,
    )


def linked_session_from_mapping(row: dict[str, object]) -> LinkedModelUsageSession:
    """Build a core linked-session value from query adapter output."""

    return LinkedModelUsageSession(
        repo_id=str(row["repo_id"]),
        host_app=str(row["host_app"]),
        host_session_key=str(row["host_session_key"]),
        thread_id=str(row["thread_id"]) if row.get("thread_id") is not None else None,
        episode_id=str(row["episode_id"]) if row.get("episode_id") is not None else None,
        transcript_path=str(row["transcript_path"]),
    )
