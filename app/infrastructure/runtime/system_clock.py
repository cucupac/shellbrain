"""Concrete wall-clock adapter."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.ports.runtime.clock import IClock


class SystemClock(IClock):
    """UTC wall-clock implementation for runtime wiring."""

    def now(self) -> datetime:
        """Return the current UTC timestamp."""

        return datetime.now(timezone.utc)
