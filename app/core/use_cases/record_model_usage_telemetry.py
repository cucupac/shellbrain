"""Thin orchestration for normalized model-usage telemetry writes."""

from __future__ import annotations

from collections.abc import Sequence

from app.core.entities.telemetry import ModelUsageRecord
from app.core.interfaces.unit_of_work import IUnitOfWork


def record_model_usage_telemetry(
    *,
    uow: IUnitOfWork,
    records: Sequence[ModelUsageRecord],
) -> None:
    """Persist normalized model-usage rows without affecting callers."""

    if not records:
        return
    uow.telemetry.insert_model_usage(tuple(records))
