"""Composition root for build_knowledge lifecycle runs."""

from __future__ import annotations

from pathlib import Path

from app.core.entities.knowledge_builder import KnowledgeBuildTrigger
from app.core.use_cases.knowledge_builder.build_knowledge import (
    BuildKnowledgeRequest,
    execute_build_knowledge,
)
from app.infrastructure.system.clock import SystemClock
from app.infrastructure.system.id_generator import UuidGenerator
from app.startup.internal_agents import (
    get_build_knowledge_inner_agent_runner,
    get_build_knowledge_settings,
)
from app.startup.use_cases import get_uow_factory


def run_build_knowledge(
    *,
    repo_id: str,
    repo_root: Path,
    episode_id: str,
    trigger: KnowledgeBuildTrigger | str,
) -> dict[str, object]:
    """Wire dependencies and run build_knowledge for one episode."""

    request = BuildKnowledgeRequest(
        repo_id=repo_id,
        repo_root=str(repo_root.resolve()),
        episode_id=episode_id,
        trigger=KnowledgeBuildTrigger(trigger),
    )
    result = execute_build_knowledge(
        request,
        uow_factory=get_uow_factory(),
        clock=SystemClock(),
        id_generator=UuidGenerator(),
        settings=get_build_knowledge_settings(),
        agent_runner=get_build_knowledge_inner_agent_runner(),
    )
    return result.to_response_data()
