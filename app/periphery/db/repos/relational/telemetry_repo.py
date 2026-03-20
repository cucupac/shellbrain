"""Relational repository for low-overhead telemetry persistence."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update

from app.core.entities.guidance import PendingUtilityCandidate
from app.core.entities.telemetry import (
    EpisodeSyncRunRecord,
    EpisodeSyncToolTypeRecord,
    OperationInvocationRecord,
    ReadResultItemRecord,
    ReadSummaryRecord,
    WriteEffectItemRecord,
    WriteSummaryRecord,
)
from app.periphery.db.models.memories import memories
from app.core.interfaces.repos import ITelemetryRepo
from app.periphery.db.models.telemetry import (
    episode_sync_runs,
    episode_sync_tool_types,
    operation_invocations,
    read_invocation_summaries,
    read_result_items,
    write_effect_items,
    write_invocation_summaries,
)
from app.periphery.db.models.utility import utility_observations


class TelemetryRepo(ITelemetryRepo):
    """Append-heavy relational persistence for operational telemetry."""

    def __init__(self, session) -> None:
        """Store the active session used to persist telemetry rows."""

        self._session = session

    def insert_operation_invocation(self, record: OperationInvocationRecord) -> None:
        """Append one parent invocation row."""

        self._session.execute(operation_invocations.insert().values(**asdict(record)))

    def insert_read_summary(
        self,
        summary: ReadSummaryRecord,
        items: tuple[ReadResultItemRecord, ...] | list[ReadResultItemRecord],
    ) -> None:
        """Replace one read summary row and its ordered result items."""

        invocation_id = summary.invocation_id
        self._session.execute(delete(read_result_items).where(read_result_items.c.invocation_id == invocation_id))
        self._session.execute(
            delete(read_invocation_summaries).where(read_invocation_summaries.c.invocation_id == invocation_id)
        )
        self._session.execute(read_invocation_summaries.insert().values(**asdict(summary)))
        if items:
            self._session.execute(read_result_items.insert(), [asdict(item) for item in items])

    def insert_write_summary(
        self,
        summary: WriteSummaryRecord,
        items: tuple[WriteEffectItemRecord, ...] | list[WriteEffectItemRecord],
    ) -> None:
        """Replace one write summary row and its ordered effect items."""

        invocation_id = summary.invocation_id
        self._session.execute(delete(write_effect_items).where(write_effect_items.c.invocation_id == invocation_id))
        self._session.execute(
            delete(write_invocation_summaries).where(write_invocation_summaries.c.invocation_id == invocation_id)
        )
        self._session.execute(write_invocation_summaries.insert().values(**asdict(summary)))
        if items:
            self._session.execute(write_effect_items.insert(), [asdict(item) for item in items])

    def insert_episode_sync_run(
        self,
        run: EpisodeSyncRunRecord,
        tool_types: tuple[EpisodeSyncToolTypeRecord, ...] | list[EpisodeSyncToolTypeRecord],
    ) -> None:
        """Append one sync-run row and its per-tool counts."""

        self._session.execute(episode_sync_runs.insert().values(**asdict(run)))
        if tool_types:
            self._session.execute(episode_sync_tool_types.insert(), [asdict(item) for item in tool_types])

    def update_operation_polling(self, invocation_id: str, *, attempted: bool, started: bool) -> None:
        """Patch poller-start bookkeeping on an existing invocation row."""

        self._session.execute(
            update(operation_invocations)
            .where(operation_invocations.c.id == invocation_id)
            .values(
                poller_start_attempted=attempted,
                poller_started=started,
            )
        )

    def list_pending_utility_candidates(
        self,
        *,
        repo_id: str,
        caller_id: str,
        problem_id: str,
        since_iso: str,
    ) -> list[PendingUtilityCandidate]:
        """Return retrieved memories that still lack a utility vote for one problem."""

        stmt = (
            select(
                read_result_items.c.memory_id,
                func.max(read_result_items.c.kind).label("kind"),
                func.count().label("retrieval_count"),
                func.max(operation_invocations.c.created_at).label("last_seen_at"),
            )
            .select_from(
                read_result_items.join(
                    operation_invocations,
                    operation_invocations.c.id == read_result_items.c.invocation_id,
                )
                .join(memories, memories.c.id == read_result_items.c.memory_id)
                .outerjoin(
                    utility_observations,
                    (utility_observations.c.memory_id == read_result_items.c.memory_id)
                    & (utility_observations.c.problem_id == problem_id),
                )
            )
            .where(
                operation_invocations.c.repo_id == repo_id,
                operation_invocations.c.command == "read",
                operation_invocations.c.outcome == "ok",
                operation_invocations.c.selected_thread_id == caller_id,
                operation_invocations.c.created_at >= _parse_iso(since_iso),
                read_result_items.c.memory_id != problem_id,
                utility_observations.c.id.is_(None),
            )
            .group_by(read_result_items.c.memory_id)
            .order_by(func.count().desc(), func.max(operation_invocations.c.created_at).desc())
        )
        rows = self._session.execute(stmt).mappings().all()
        return [
            PendingUtilityCandidate(
                memory_id=str(row["memory_id"]),
                kind=str(row["kind"]),
                retrieval_count=int(row["retrieval_count"]),
                last_seen_at=row["last_seen_at"].isoformat(),
            )
            for row in rows
        ]


def _parse_iso(value: str) -> datetime:
    """Parse one ISO timestamp into a timezone-aware datetime."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
