"""Thin orchestration for sync-run telemetry writes."""

from __future__ import annotations

from collections.abc import Sequence

from app.core.entities.telemetry import EpisodeSyncRunRecord, EpisodeSyncToolTypeRecord
from app.core.interfaces.unit_of_work import IUnitOfWork


def record_episode_sync_telemetry(
    *,
    uow: IUnitOfWork,
    run: EpisodeSyncRunRecord,
    tool_types: Sequence[EpisodeSyncToolTypeRecord] = (),
) -> None:
    """Persist one sync-run row and its per-tool aggregates."""

    uow.telemetry.insert_episode_sync_run(run, tuple(tool_types))
