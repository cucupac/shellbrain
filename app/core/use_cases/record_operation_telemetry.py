"""Thin orchestration for operation-level telemetry writes."""

from __future__ import annotations

from collections.abc import Sequence

from app.core.entities.telemetry import (
    OperationInvocationRecord,
    RecallSourceItemRecord,
    RecallSummaryRecord,
    ReadResultItemRecord,
    ReadSummaryRecord,
    WriteEffectItemRecord,
    WriteSummaryRecord,
)
from app.core.interfaces.unit_of_work import IUnitOfWork


def record_operation_telemetry(
    *,
    uow: IUnitOfWork,
    invocation: OperationInvocationRecord,
    read_summary: ReadSummaryRecord | None = None,
    read_items: Sequence[ReadResultItemRecord] = (),
    recall_summary: RecallSummaryRecord | None = None,
    recall_items: Sequence[RecallSourceItemRecord] = (),
    write_summary: WriteSummaryRecord | None = None,
    write_items: Sequence[WriteEffectItemRecord] = (),
) -> None:
    """Persist one invocation row and any attached read or write summaries."""

    uow.telemetry.insert_operation_invocation(invocation)
    if read_summary is not None:
        uow.telemetry.insert_read_summary(read_summary, tuple(read_items))
    if recall_summary is not None:
        uow.telemetry.insert_recall_summary(recall_summary, tuple(recall_items))
    if write_summary is not None:
        uow.telemetry.insert_write_summary(write_summary, tuple(write_items))
