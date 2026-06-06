"""Pure freshness policy for generated wiki summaries."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.entities.wiki_summaries import (
    WikiSummaryFreshness,
    WikiSummaryGenerationStatus,
    WikiSummaryInputSnapshot,
    WikiSummaryRecord,
    WikiSummarySourceVelocity,
)


_EXPIRATION_BY_VELOCITY = {
    WikiSummarySourceVelocity.HIGH: timedelta(days=3),
    WikiSummarySourceVelocity.NORMAL: timedelta(days=14),
    WikiSummarySourceVelocity.QUIET: timedelta(days=60),
}


def determine_wiki_summary_freshness(
    *,
    record: WikiSummaryRecord | None,
    snapshot: WikiSummaryInputSnapshot,
    now: datetime,
) -> tuple[WikiSummaryFreshness, str | None]:
    """Return freshness and a compact reason for one cached summary."""

    if record is None:
        return WikiSummaryFreshness.MISSING, "summary has not been generated"
    if record.generation_status == WikiSummaryGenerationStatus.PENDING:
        return WikiSummaryFreshness.PENDING, "summary generation is running"
    if record.generation_status == WikiSummaryGenerationStatus.FAILED:
        reason = record.last_error_code or "generation failed"
        return WikiSummaryFreshness.FAILED, reason
    if record.input_hash != snapshot.input_hash:
        return WikiSummaryFreshness.STALE, "source facts changed"
    if record.generated_at is None:
        return WikiSummaryFreshness.STALE, "summary has no generated timestamp"

    ttl = _EXPIRATION_BY_VELOCITY[snapshot.source_velocity]
    if now - record.generated_at > ttl:
        return WikiSummaryFreshness.EXPIRED, (
            f"{snapshot.source_velocity.value} velocity summary exceeded "
            f"{ttl.days} day freshness window"
        )
    return WikiSummaryFreshness.FRESH, None


def needs_wiki_summary_refresh(freshness: WikiSummaryFreshness) -> bool:
    """Return whether this freshness state should enqueue background refresh."""

    return freshness in {
        WikiSummaryFreshness.MISSING,
        WikiSummaryFreshness.STALE,
        WikiSummaryFreshness.EXPIRED,
        WikiSummaryFreshness.FAILED,
    }
