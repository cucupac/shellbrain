"""Memory recall use case."""

from app.core.use_cases.retrieval.recall.request import (
    MemoryRecallRequest,
    RecallCurrentProblem,
)
from app.core.use_cases.retrieval.recall.result import RecallMemoryResult

__all__ = [
    "MemoryRecallRequest",
    "RecallCurrentProblem",
    "RecallMemoryResult",
    "execute_recall_memory",
]


def __getattr__(name: str):
    if name == "execute_recall_memory":
        from app.core.use_cases.retrieval.recall.execute import execute_recall_memory

        return execute_recall_memory
    raise AttributeError(name)
