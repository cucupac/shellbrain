"""Memory update use case."""

from app.core.use_cases.memories.update.request import (
    MemoryBatchUpdateRequest,
    MemoryUpdateRequest,
)
from app.core.use_cases.memories.update.result import (
    BatchUpdateMemoryResult,
    UpdateMemoryResult,
)

__all__ = [
    "BatchUpdateMemoryResult",
    "MemoryBatchUpdateRequest",
    "MemoryUpdateRequest",
    "UpdateMemoryResult",
    "execute_update_memory",
]


def __getattr__(name: str):
    if name == "execute_update_memory":
        from app.core.use_cases.memories.update.execute import execute_update_memory

        return execute_update_memory
    raise AttributeError(name)
