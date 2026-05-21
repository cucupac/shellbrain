"""Pure build_knowledge trigger planning for stable episode watermarks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.entities.episodes import EpisodeBuildSnapshot, EpisodeStatus
from app.core.entities.knowledge_builder import KnowledgeBuildTrigger


@dataclass(frozen=True)
class KnowledgeBuildPlan:
    """One planned build_knowledge run for an episode."""

    episode_id: str
    trigger: KnowledgeBuildTrigger
    baseline_only: bool = False


def plan_stable_watermark_builds(
    *,
    snapshots: Iterable[EpisodeBuildSnapshot],
    now: datetime,
    idle_stable_seconds: int,
    lifecycle_activated_at: datetime | None = None,
) -> tuple[KnowledgeBuildPlan, ...]:
    """Return build plans for closed or idle-stable episodes with new events."""

    if idle_stable_seconds < 0:
        raise ValueError("idle_stable_seconds must be non-negative")
    stable_before = now - timedelta(seconds=idle_stable_seconds)
    legacy_baseline_before = (
        None
        if lifecycle_activated_at is None
        else lifecycle_activated_at - timedelta(seconds=idle_stable_seconds)
    )
    plans: list[KnowledgeBuildPlan] = []
    seen: set[str] = set()
    for snapshot in snapshots:
        if snapshot.episode_id in seen:
            continue
        if not _has_unbuilt_events(snapshot):
            continue
        if not _is_stable_build_candidate(
            snapshot=snapshot,
            stable_before=stable_before,
        ):
            continue
        seen.add(snapshot.episode_id)
        plans.append(
            KnowledgeBuildPlan(
                episode_id=snapshot.episode_id,
                trigger=KnowledgeBuildTrigger.WATERMARK_STABLE,
                baseline_only=_should_baseline_legacy_first_build(
                    snapshot=snapshot,
                    legacy_baseline_before=legacy_baseline_before,
                ),
            )
        )
    return tuple(plans)


def _has_unbuilt_events(snapshot: EpisodeBuildSnapshot) -> bool:
    """Return whether the episode has events beyond the last successful build."""

    return snapshot.latest_event_seq > (
        snapshot.latest_successful_build_watermark or 0
    )


def _is_stable_build_candidate(
    *, snapshot: EpisodeBuildSnapshot, stable_before: datetime
) -> bool:
    """Return whether an episode is stable enough to consolidate its watermark."""

    if snapshot.status is EpisodeStatus.CLOSED:
        return True
    if snapshot.status is not EpisodeStatus.ACTIVE:
        return False
    return snapshot.latest_event_at <= stable_before


def _should_baseline_legacy_first_build(
    *,
    snapshot: EpisodeBuildSnapshot,
    legacy_baseline_before: datetime | None,
) -> bool:
    """Return whether an old first-build episode should be watermarked only."""

    if legacy_baseline_before is None:
        return False
    if snapshot.latest_successful_build_watermark is not None:
        return False
    return snapshot.latest_event_at <= legacy_baseline_before
