"""Concrete UUID identifier generator."""

from __future__ import annotations

from uuid import uuid4

from app.core.ports.system.idgen import IIdGenerator


class UuidGenerator(IIdGenerator):
    """String UUID generator for runtime wiring."""

    def new_id(self) -> str:
        """Return one new UUID string."""

        return str(uuid4())
