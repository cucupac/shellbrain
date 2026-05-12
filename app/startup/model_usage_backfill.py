"""Wiring for retroactive token-usage backfill."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.core.use_cases.admin.backfill_model_usage import (
    BackfillModelUsageRequest,
    BackfillSummary,
    backfill_model_usage as execute_backfill_model_usage,
    linked_session_from_mapping,
)
from app.infrastructure.db.runtime.queries.model_usage_backfill import (
    load_linked_model_usage_sessions,
)
from app.infrastructure.host_apps.transcripts.model_usage import (
    collect_model_usage_records_for_session,
)
from app.infrastructure.telemetry.recorder import record_model_usage_telemetry
from app.startup.use_cases import get_uow_factory


def backfill_model_usage(*, engine: Any) -> BackfillSummary:
    """Build concrete adapters and run model-usage backfill."""

    sessions = tuple(
        linked_session_from_mapping(row)
        for row in load_linked_model_usage_sessions(engine=engine)
    )
    uow_factory = get_uow_factory()

    def _persist_records(records: Sequence[object]) -> None:
        with uow_factory() as uow:
            record_model_usage_telemetry(uow=uow, records=tuple(records))

    return execute_backfill_model_usage(
        BackfillModelUsageRequest(sessions=sessions),
        collect_model_usage_records_for_session=collect_model_usage_records_for_session,
        persist_model_usage_records=_persist_records,
    )
