"""Best-effort telemetry patching for operation poller startup state."""

from __future__ import annotations


def update_operation_polling_status(
    *, uow_factory, invocation_id: str, attempted: bool, started: bool
) -> None:
    """Patch poller-start telemetry flags without affecting the visible command result."""

    try:
        with uow_factory() as uow:
            uow.telemetry.update_operation_polling(
                invocation_id,
                attempted=attempted,
                started=started,
            )
    except Exception:
        return
