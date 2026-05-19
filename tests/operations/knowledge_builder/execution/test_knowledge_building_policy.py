"""Pure policy tests for knowledge-builder stable-watermark planning."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.entities.episodes import EpisodeBuildSnapshot, EpisodeStatus
from app.core.entities.knowledge_builder import KnowledgeBuildTrigger
from app.core.policies.episodes.knowledge_building import (
    KnowledgeBuildPlan,
    plan_stable_watermark_builds,
)


NOW = datetime(2026, 5, 19, 12, tzinfo=timezone.utc)
OLD = datetime(2026, 5, 19, 11, 30, tzinfo=timezone.utc)
RECENT = datetime(2026, 5, 19, 11, 59, 30, tzinfo=timezone.utc)


def test_active_stable_unbuilt_episode_should_plan_watermark_build() -> None:
    plans = plan_stable_watermark_builds(
        snapshots=(
            _snapshot(
                episode_id="ep-1",
                status=EpisodeStatus.ACTIVE,
                latest_event_seq=8,
                latest_event_at=OLD,
                latest_successful_build_watermark=3,
            ),
        ),
        now=NOW,
        idle_stable_seconds=900,
    )

    assert plans == (
        KnowledgeBuildPlan(
            episode_id="ep-1",
            trigger=KnowledgeBuildTrigger.WATERMARK_STABLE,
        ),
    )


def test_active_recent_episode_should_not_build_yet() -> None:
    plans = plan_stable_watermark_builds(
        snapshots=(
            _snapshot(
                episode_id="ep-1",
                status=EpisodeStatus.ACTIVE,
                latest_event_seq=8,
                latest_event_at=RECENT,
                latest_successful_build_watermark=3,
            ),
        ),
        now=NOW,
        idle_stable_seconds=900,
    )

    assert plans == ()


def test_closed_episode_with_unbuilt_events_should_build_immediately() -> None:
    plans = plan_stable_watermark_builds(
        snapshots=(
            _snapshot(
                episode_id="ep-1",
                status=EpisodeStatus.CLOSED,
                latest_event_seq=8,
                latest_event_at=RECENT,
                latest_successful_build_watermark=3,
            ),
        ),
        now=NOW,
        idle_stable_seconds=900,
    )

    assert plans == (
        KnowledgeBuildPlan(
            episode_id="ep-1",
            trigger=KnowledgeBuildTrigger.WATERMARK_STABLE,
        ),
    )


def test_current_watermark_should_not_build_again() -> None:
    plans = plan_stable_watermark_builds(
        snapshots=(
            _snapshot(
                episode_id="ep-1",
                status=EpisodeStatus.ACTIVE,
                latest_event_seq=8,
                latest_event_at=OLD,
                latest_successful_build_watermark=8,
            ),
        ),
        now=NOW,
        idle_stable_seconds=900,
    )

    assert plans == ()


def test_archived_episode_should_not_build() -> None:
    plans = plan_stable_watermark_builds(
        snapshots=(
            _snapshot(
                episode_id="ep-1",
                status=EpisodeStatus.ARCHIVED,
                latest_event_seq=8,
                latest_event_at=OLD,
                latest_successful_build_watermark=3,
            ),
        ),
        now=NOW,
        idle_stable_seconds=900,
    )

    assert plans == ()


def test_stable_planner_should_deduplicate_episode_ids() -> None:
    plans = plan_stable_watermark_builds(
        snapshots=(
            _snapshot(
                episode_id="ep-1",
                status=EpisodeStatus.ACTIVE,
                latest_event_seq=8,
                latest_event_at=OLD,
                latest_successful_build_watermark=3,
            ),
            _snapshot(
                episode_id="ep-1",
                status=EpisodeStatus.ACTIVE,
                latest_event_seq=9,
                latest_event_at=OLD,
                latest_successful_build_watermark=3,
            ),
        ),
        now=NOW,
        idle_stable_seconds=900,
    )

    assert plans == (
        KnowledgeBuildPlan(
            episode_id="ep-1",
            trigger=KnowledgeBuildTrigger.WATERMARK_STABLE,
        ),
    )


def test_stable_planner_should_reject_negative_idle_window() -> None:
    with pytest.raises(ValueError, match="idle_stable_seconds"):
        plan_stable_watermark_builds(
            snapshots=(),
            now=NOW,
            idle_stable_seconds=-1,
        )


def _snapshot(
    *,
    episode_id: str,
    status: EpisodeStatus,
    latest_event_seq: int,
    latest_event_at: datetime,
    latest_successful_build_watermark: int | None,
) -> EpisodeBuildSnapshot:
    return EpisodeBuildSnapshot(
        episode_id=episode_id,
        status=status,
        latest_event_seq=latest_event_seq,
        latest_event_at=latest_event_at,
        latest_successful_build_watermark=latest_successful_build_watermark,
    )
