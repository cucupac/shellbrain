"""Persistence support for operation-level telemetry records."""

from __future__ import annotations

from collections.abc import Sequence

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
from app.infrastructure.telemetry.storage_protocols import TelemetryUnitOfWork


def record_operation_telemetry(
    *,
    uow: TelemetryUnitOfWork,
    invocation: OperationInvocationRecord,
    read_summary: ReadSummaryRecord | None = None,
    read_items: Sequence[ReadResultItemRecord] = (),
    recall_summary: RecallSummaryRecord | None = None,
    recall_items: Sequence[RecallSourceItemRecord] = (),
    inner_agent_invocations: Sequence[InnerAgentInvocationRecord] = (),
    write_summary: WriteSummaryRecord | None = None,
    write_items: Sequence[WriteEffectItemRecord] = (),
) -> None:
    """Persist one invocation row and any attached read or write summaries."""

    uow.telemetry.insert_operation_invocation(invocation)
    if read_summary is not None:
        uow.telemetry.insert_read_summary(read_summary, tuple(read_items))
    if recall_summary is not None:
        uow.telemetry.insert_recall_summary(recall_summary, tuple(recall_items))
    if inner_agent_invocations:
        uow.telemetry.insert_inner_agent_invocations(tuple(inner_agent_invocations))
    if write_summary is not None:
        uow.telemetry.insert_write_summary(write_summary, tuple(write_items))


def record_episode_sync_telemetry(
    *,
    uow: TelemetryUnitOfWork,
    run: EpisodeSyncRunRecord,
    tool_types: Sequence[EpisodeSyncToolTypeRecord] = (),
) -> None:
    """Persist one sync-run row and its per-tool aggregates."""

    uow.telemetry.insert_episode_sync_run(run, tuple(tool_types))


def record_model_usage_telemetry(
    *,
    uow: TelemetryUnitOfWork,
    records: Sequence[ModelUsageRecord],
) -> None:
    """Persist normalized model-usage rows without affecting callers."""

    if not records:
        return
    uow.telemetry.insert_model_usage(tuple(records))
