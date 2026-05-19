"""Pure policy tests for knowledge-builder lifecycle planning."""

from __future__ import annotations

from app.core.entities.knowledge_builder import KnowledgeBuildTrigger
from app.core.policies.episodes.knowledge_building import (
    KnowledgeBuildPlan,
    plan_idle_stable_builds,
    plan_replacement_build,
)


def test_replacement_build_prefers_closed_episode_id() -> None:
    plan = plan_replacement_build(
        previous_episode_id="ep-previous",
        closed_episode_id="ep-closed",
    )

    assert plan == KnowledgeBuildPlan(
        episode_id="ep-closed",
        trigger=KnowledgeBuildTrigger.SESSION_REPLACED,
    )


def test_replacement_build_falls_back_to_previous_episode_id() -> None:
    plan = plan_replacement_build(
        previous_episode_id="ep-previous",
        closed_episode_id=None,
    )

    assert plan == KnowledgeBuildPlan(
        episode_id="ep-previous",
        trigger=KnowledgeBuildTrigger.SESSION_REPLACED,
    )


def test_replacement_build_skips_when_no_episode_is_known() -> None:
    assert (
        plan_replacement_build(previous_episode_id=None, closed_episode_id=None)
        is None
    )


def test_idle_stable_builds_deduplicate_known_episode_ids() -> None:
    plans = plan_idle_stable_builds(("ep-a", None, "ep-b", "ep-a"))

    assert plans == (
        KnowledgeBuildPlan(
            episode_id="ep-a",
            trigger=KnowledgeBuildTrigger.IDLE_STABLE,
        ),
        KnowledgeBuildPlan(
            episode_id="ep-b",
            trigger=KnowledgeBuildTrigger.IDLE_STABLE,
        ),
    )
