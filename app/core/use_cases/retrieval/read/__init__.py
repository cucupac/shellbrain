"""Memory read use case."""

from app.core.use_cases.retrieval.read.request import (
    MemoryReadRequest,
    ReadConceptsExpandRequest,
    ReadExpandRequest,
)
from app.core.use_cases.retrieval.read.result import ReadMemoryResult

__all__ = [
    "MemoryReadRequest",
    "ReadConceptsExpandRequest",
    "ReadExpandRequest",
    "ReadMemoryResult",
    "build_context_pack",
    "execute_read_memory",
]


def __getattr__(name: str):
    if name == "build_context_pack":
        from app.core.use_cases.retrieval.context_pack_pipeline import build_context_pack

        return build_context_pack
    if name == "execute_read_memory":
        from app.core.use_cases.retrieval.read.execute import execute_read_memory

        return execute_read_memory
    raise AttributeError(name)
