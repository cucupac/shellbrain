"""Infrastructure-only ports for telemetry persistence."""

from __future__ import annotations

from typing import Protocol, Sequence


class TelemetryWriteRepository(Protocol):
    """Append-heavy telemetry persistence protocol."""

    def insert_operation_invocation(self, record: object) -> None:
        """Append one command-level telemetry row."""

    def insert_read_summary(
        self,
        summary: object,
        items: Sequence[object],
    ) -> None:
        """Persist one read summary row and its ordered result items."""

    def insert_recall_summary(
        self,
        summary: object,
        items: Sequence[object],
    ) -> None:
        """Persist one recall summary row and its ordered source items."""

    def insert_write_summary(
        self,
        summary: object,
        items: Sequence[object],
    ) -> None:
        """Persist one write summary row and its ordered effect items."""

    def insert_episode_sync_run(
        self,
        run: object,
        tool_types: Sequence[object],
    ) -> None:
        """Append one sync-run row and its per-tool aggregates."""

    def insert_model_usage(self, records: Sequence[object]) -> None:
        """Append normalized model-usage rows idempotently."""

    def update_operation_polling(
        self, invocation_id: str, *, attempted: bool, started: bool
    ) -> None:
        """Patch poller-start bookkeeping on an existing invocation row."""


class TelemetryUnitOfWork(Protocol):
    """Transaction protocol required by telemetry recorders."""

    telemetry: TelemetryWriteRepository

    def commit(self) -> None:
        """Commit the current transaction."""

    def rollback(self) -> None:
        """Roll back the current transaction."""
