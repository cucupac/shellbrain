"""Retrieval use-case execution with injected handler settings."""

from __future__ import annotations

from app.core.contracts.responses import UseCaseResult
from app.core.use_cases.retrieval.recall import execute_recall_memory
from app.core.use_cases.retrieval.read import execute_read_memory
from app.entrypoints.cli.handlers.command_context import OperationDependencies


def execute_read_memory_with_dependencies(
    *, request, uow, dependencies: OperationDependencies
) -> UseCaseResult:
    """Execute read with handler-injected retrieval settings."""

    return execute_read_memory(
        request,
        uow,
        read_settings=dependencies.read_settings,
        threshold_settings=dependencies.threshold_settings,
    )


def execute_recall_memory_with_dependencies(
    *, request, uow, dependencies: OperationDependencies
) -> UseCaseResult:
    """Execute recall with handler-injected retrieval settings."""

    return execute_recall_memory(
        request,
        uow,
        read_settings=dependencies.read_settings,
        threshold_settings=dependencies.threshold_settings,
    )
