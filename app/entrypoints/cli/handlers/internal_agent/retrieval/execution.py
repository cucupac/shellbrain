"""Retrieval use-case execution with injected handler settings."""

from __future__ import annotations

from app.core.use_cases.retrieval.recall import execute_recall_memory
from app.core.use_cases.retrieval.recall.result import RecallMemoryResult
from app.core.use_cases.retrieval.read import execute_read_memory
from app.core.use_cases.retrieval.read.result import ReadMemoryResult
from app.startup.operation_dependencies import OperationDependencies


def execute_read_memory_with_dependencies(
    *, request, uow, dependencies: OperationDependencies
) -> ReadMemoryResult:
    """Execute read with handler-injected retrieval settings."""

    return execute_read_memory(
        request,
        uow,
        read_settings=dependencies.read_settings,
        threshold_settings=dependencies.threshold_settings,
    )


def execute_recall_memory_with_dependencies(
    *, request, uow, dependencies: OperationDependencies, repo_root: str | None = None
) -> RecallMemoryResult:
    """Execute recall with handler-injected retrieval settings."""

    return execute_recall_memory(
        request,
        uow,
        read_settings=dependencies.read_settings,
        threshold_settings=dependencies.threshold_settings,
        inner_agent_runner=dependencies.build_context_inner_agent_runner,
        build_context_settings=dependencies.build_context_settings,
        repo_root=repo_root,
    )
