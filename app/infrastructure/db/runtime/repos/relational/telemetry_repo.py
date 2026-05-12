"""Relational repository for low-overhead telemetry persistence."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.entities.guidance import PendingUtilityCandidate
from app.core.ports.db.guidance import IPendingUtilityCandidatesRepo
from app.infrastructure.db.runtime.models.memories import memories
from app.infrastructure.db.runtime.models.telemetry import (
    episode_sync_runs,
    episode_sync_tool_types,
    inner_agent_invocations,
    model_usage,
    operation_invocations,
    recall_invocation_summaries,
    recall_source_items,
    read_invocation_summaries,
    read_result_items,
    write_effect_items,
    write_invocation_summaries,
)
from app.infrastructure.db.runtime.models.utility import utility_observations
from app.infrastructure.telemetry.records import (
    EpisodeSyncRunRecord,
    EpisodeSyncToolTypeRecord,
    InnerAgentInvocationRecord,
    ModelUsageRecord,
    OperationInvocationRecord,
    RecallSourceItemRecord,
    RecallSummaryRecord,
    ReadResultItemRecord,
    ReadSummaryRecord,
    WriteEffectItemRecord,
    WriteSummaryRecord,
)


class TelemetryRepo(IPendingUtilityCandidatesRepo):
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
        self._session.execute(
            delete(read_result_items).where(
                read_result_items.c.invocation_id == invocation_id
            )
        )
        self._session.execute(
            delete(read_invocation_summaries).where(
                read_invocation_summaries.c.invocation_id == invocation_id
            )
        )
        self._session.execute(
            read_invocation_summaries.insert().values(**asdict(summary))
        )
        if items:
            self._session.execute(
                read_result_items.insert(), [asdict(item) for item in items]
            )

    def insert_recall_summary(
        self,
        summary: RecallSummaryRecord,
        items: tuple[RecallSourceItemRecord, ...] | list[RecallSourceItemRecord],
    ) -> None:
        """Replace one recall summary row and its ordered source items."""

        invocation_id = summary.invocation_id
        self._session.execute(
            delete(recall_source_items).where(
                recall_source_items.c.invocation_id == invocation_id
            )
        )
        self._session.execute(
            delete(recall_invocation_summaries).where(
                recall_invocation_summaries.c.invocation_id == invocation_id
            )
        )
        self._session.execute(
            recall_invocation_summaries.insert().values(**asdict(summary))
        )
        if items:
            self._session.execute(
                recall_source_items.insert(), [asdict(item) for item in items]
            )

    def insert_inner_agent_invocations(
        self,
        records: tuple[InnerAgentInvocationRecord, ...]
        | list[InnerAgentInvocationRecord],
    ) -> None:
        """Append inner-agent invocation rows."""

        if records:
            operation_ids = {record.operation_invocation_id for record in records}
            self._session.execute(
                delete(inner_agent_invocations).where(
                    inner_agent_invocations.c.operation_invocation_id.in_(
                        operation_ids
                    )
                )
            )
            self._session.execute(
                inner_agent_invocations.insert(), [asdict(record) for record in records]
            )

    def insert_write_summary(
        self,
        summary: WriteSummaryRecord,
        items: tuple[WriteEffectItemRecord, ...] | list[WriteEffectItemRecord],
    ) -> None:
        """Replace one write summary row and its ordered effect items."""

        invocation_id = summary.invocation_id
        self._session.execute(
            delete(write_effect_items).where(
                write_effect_items.c.invocation_id == invocation_id
            )
        )
        self._session.execute(
            delete(write_invocation_summaries).where(
                write_invocation_summaries.c.invocation_id == invocation_id
            )
        )
        self._session.execute(
            write_invocation_summaries.insert().values(**asdict(summary))
        )
        if items:
            self._session.execute(
                write_effect_items.insert(), [asdict(item) for item in items]
            )

    def insert_episode_sync_run(
        self,
        run: EpisodeSyncRunRecord,
        tool_types: tuple[EpisodeSyncToolTypeRecord, ...]
        | list[EpisodeSyncToolTypeRecord],
    ) -> None:
        """Append one sync-run row and its per-tool counts."""

        self._session.execute(episode_sync_runs.insert().values(**asdict(run)))
        if tool_types:
            self._session.execute(
                episode_sync_tool_types.insert(), [asdict(item) for item in tool_types]
            )

    def insert_model_usage(
        self, records: tuple[ModelUsageRecord, ...] | list[ModelUsageRecord]
    ) -> None:
        """Append normalized model-usage rows idempotently."""

        if not records:
            return
        rows = []
        for record in records:
            payload = asdict(record)
            if payload["created_at"] is None:
                payload["created_at"] = datetime.now(timezone.utc)
            rows.append(payload)
        statement = pg_insert(model_usage).values(rows)
        statement = statement.on_conflict_do_nothing(
            constraint="uq_model_usage_host_session_usage"
        )
        self._session.execute(statement)

    def update_operation_polling(
        self, invocation_id: str, *, attempted: bool, started: bool
    ) -> None:
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
            .order_by(
                func.count().desc(), func.max(operation_invocations.c.created_at).desc()
            )
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
