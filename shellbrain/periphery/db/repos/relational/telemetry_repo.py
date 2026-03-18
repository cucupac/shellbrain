"""Relational repository for low-overhead telemetry persistence."""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import delete, update

from shellbrain.core.entities.telemetry import (
    EpisodeSyncRunRecord,
    EpisodeSyncToolTypeRecord,
    OperationInvocationRecord,
    ReadResultItemRecord,
    ReadSummaryRecord,
    WriteEffectItemRecord,
    WriteSummaryRecord,
)
from shellbrain.core.interfaces.repos import ITelemetryRepo
from shellbrain.periphery.db.models.telemetry import (
    episode_sync_runs,
    episode_sync_tool_types,
    operation_invocations,
    read_invocation_summaries,
    read_result_items,
    write_effect_items,
    write_invocation_summaries,
)


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
