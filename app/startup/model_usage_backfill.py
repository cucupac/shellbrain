"""Retroactive token-usage backfill from Shellbrain-linked host transcripts."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.startup.use_cases import get_uow_factory
from app.core.entities.telemetry import ModelUsageRecord
from app.core.use_cases.record_model_usage_telemetry import record_model_usage_telemetry
from app.periphery.host_transcripts.model_usage import collect_model_usage_records_for_session


@dataclass(frozen=True)
class BackfillSummary:
    """Small structured summary for token-usage backfill runs."""

    sessions_examined: int
    sessions_with_records: int
    sessions_skipped: int
    sessions_failed: int
    records_attempted: int
    host_counts: dict[str, int]
    errors: list[dict[str, str]]

    def to_payload(self) -> dict[str, object]:
        """Render the summary into JSON-safe primitives."""

        return {
            "sessions_examined": self.sessions_examined,
            "sessions_with_records": self.sessions_with_records,
            "sessions_skipped": self.sessions_skipped,
            "sessions_failed": self.sessions_failed,
            "records_attempted": self.records_attempted,
            "host_counts": self.host_counts,
            "errors": self.errors,
        }


def backfill_model_usage(*, engine: Engine) -> BackfillSummary:
    """Backfill normalized model usage for all Shellbrain-linked historical sessions."""

    rows = _load_linked_sessions(engine=engine)
    host_counts: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    sessions_with_records = 0
    sessions_skipped = 0
    sessions_failed = 0
    records_attempted = 0
    uow_factory = get_uow_factory()

    for row in rows:
        transcript_path = Path(str(row["transcript_path"]))
        try:
            records = collect_model_usage_records_for_session(
                repo_id=str(row["repo_id"]),
                host_app=str(row["host_app"]),
                host_session_key=str(row["host_session_key"]),
                thread_id=str(row["thread_id"]) if row["thread_id"] is not None else None,
                episode_id=str(row["episode_id"]) if row["episode_id"] is not None else None,
                transcript_path=transcript_path,
            )
        except Exception as exc:
            sessions_failed += 1
            errors.append(
                {
                    "host_app": str(row["host_app"]),
                    "host_session_key": str(row["host_session_key"]),
                    "message": str(exc),
                }
            )
            continue

        if not records:
            sessions_skipped += 1
            continue
        _persist_records(uow_factory=uow_factory, records=records)
        sessions_with_records += 1
        records_attempted += len(records)
        host_counts[str(row["host_app"])] += len(records)

    return BackfillSummary(
        sessions_examined=len(rows),
        sessions_with_records=sessions_with_records,
        sessions_skipped=sessions_skipped,
        sessions_failed=sessions_failed,
        records_attempted=records_attempted,
        host_counts=dict(sorted(host_counts.items())),
        errors=errors,
    )


def _persist_records(*, uow_factory, records: list[ModelUsageRecord]) -> None:
    """Persist a batch of model-usage rows in one transaction."""

    with uow_factory() as uow:
        record_model_usage_telemetry(uow=uow, records=tuple(records))


def _load_linked_sessions(*, engine: Engine) -> list[dict[str, object]]:
    """Return the latest Shellbrain-linked sync record per repo/host/session."""

    statement = text(
        """
        SELECT DISTINCT ON (repo_id, host_app, host_session_key)
          repo_id,
          host_app,
          host_session_key,
          thread_id,
          episode_id,
          transcript_path
        FROM episode_sync_runs
        WHERE episode_id IS NOT NULL
          AND transcript_path IS NOT NULL
        ORDER BY repo_id, host_app, host_session_key, created_at DESC, id DESC
        """
    )
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(statement).mappings().all()]
