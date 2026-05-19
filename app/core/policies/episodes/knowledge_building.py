"""Pure build_knowledge trigger planning for episode lifecycle events."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.core.entities.knowledge_builder import KnowledgeBuildTrigger


@dataclass(frozen=True)
class KnowledgeBuildPlan:
    """One planned build_knowledge run for an episode."""

    episode_id: str
    trigger: KnowledgeBuildTrigger


def plan_replacement_build(
    *, previous_episode_id: str | None, closed_episode_id: str | None
) -> KnowledgeBuildPlan | None:
    """Return the build plan for a replaced session, if an episode is known."""

    episode_id = closed_episode_id or previous_episode_id
    if episode_id is None:
        return None
    return KnowledgeBuildPlan(
        episode_id=episode_id,
        trigger=KnowledgeBuildTrigger.SESSION_REPLACED,
    )


def plan_idle_stable_builds(
    episode_ids: Iterable[str | None],
) -> tuple[KnowledgeBuildPlan, ...]:
    """Return deduplicated idle-stable build plans for known active episodes."""

    plans: list[KnowledgeBuildPlan] = []
    seen: set[str] = set()
    for episode_id in episode_ids:
        if episode_id is None or episode_id in seen:
            continue
        seen.add(episode_id)
        plans.append(
            KnowledgeBuildPlan(
                episode_id=episode_id,
                trigger=KnowledgeBuildTrigger.IDLE_STABLE,
            )
        )
    return tuple(plans)
