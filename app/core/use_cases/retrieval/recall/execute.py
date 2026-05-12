"""This module defines the worker-facing recall orchestration entry point."""

from __future__ import annotations

from app.core.entities.inner_agents import InnerAgentSettings
from app.core.entities.settings import (
    ReadPolicySettings,
    ThresholdSettings,
)
from app.core.ports.db.unit_of_work import IUnitOfWork
from app.core.ports.host_apps.inner_agents import IInnerAgentRunner
from app.core.use_cases.retrieval.build_context import execute_build_context
from app.core.use_cases.retrieval.recall.request import MemoryRecallRequest
from app.core.use_cases.retrieval.recall.result import RecallMemoryResult


def execute_recall_memory(
    request: MemoryRecallRequest,
    uow: IUnitOfWork,
    *,
    read_settings: ReadPolicySettings | None = None,
    threshold_settings: ThresholdSettings | None = None,
    inner_agent_runner: IInnerAgentRunner | None = None,
    build_context_settings: InnerAgentSettings | None = None,
    repo_root: str | None = None,
) -> RecallMemoryResult:
    """Run the read-only build_context workflow and return a recall brief."""

    return execute_build_context(
        request,
        uow,
        read_settings=read_settings,
        threshold_settings=threshold_settings,
        inner_agent_runner=inner_agent_runner,
        build_context_settings=build_context_settings,
        repo_root=repo_root,
    )
