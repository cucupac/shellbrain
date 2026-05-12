"""Memory add use case."""

from app.core.use_cases.memories.add.request import MemoryAddRequest
from app.core.use_cases.memories.add.result import CreateMemoryResult

__all__ = ["CreateMemoryResult", "MemoryAddRequest", "execute_create_memory"]


def __getattr__(name: str):
    if name == "execute_create_memory":
        from app.core.use_cases.memories.add.execute import execute_create_memory

        return execute_create_memory
    raise AttributeError(name)
