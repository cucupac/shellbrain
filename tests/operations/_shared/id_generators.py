"""Deterministic ID generators for operation use-case tests."""

from app.core.ports.system.idgen import IIdGenerator


class SequenceIdGenerator(IIdGenerator):
    def __init__(self, prefix: str = "test-id") -> None:
        self._prefix = prefix
        self._next = 0

    def new_id(self) -> str:
        self._next += 1
        return f"{self._prefix}-{self._next}"
