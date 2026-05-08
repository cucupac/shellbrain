"""Retrieval use-case execution with optional dependency compatibility."""

from __future__ import annotations

from app.core.contracts.responses import OperationResult
from app.core.use_cases.agent_operations.dependencies import OperationDependencies
from app.core.use_cases.memory_retrieval.recall_memory import execute_recall_memory
from app.core.use_cases.memory_retrieval.read_memory import execute_read_memory


def execute_read_memory_with_dependencies(*, request, uow, dependencies: OperationDependencies) -> OperationResult:
    """Execute read with injected settings while preserving older test doubles."""

    try:
        return execute_read_memory(
            request,
            uow,
            read_settings=dependencies.read_settings,
            threshold_settings=dependencies.threshold_settings,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return execute_read_memory(request, uow)


def execute_recall_memory_with_dependencies(*, request, uow, dependencies: OperationDependencies) -> OperationResult:
    """Execute recall with injected settings while preserving older test doubles."""

    try:
        return execute_recall_memory(
            request,
            uow,
            read_settings=dependencies.read_settings,
            threshold_settings=dependencies.threshold_settings,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return execute_recall_memory(request, uow)
