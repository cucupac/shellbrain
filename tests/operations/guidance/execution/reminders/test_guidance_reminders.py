"""Guidance reminder contracts."""

from app.core.entities.guidance import GuidanceDecision
from app.core.use_cases.build_guidance import should_emit_guidance_reminder


def test_guidance_reminders_should_be_rate_limited_per_problem() -> None:
    """guidance reminders should always be rate limited per problem."""

    decision = GuidanceDecision(
        code="pending_utility_votes",
        severity="info",
        message="Pending votes.",
        problem_id="problem-1",
    )

    assert (
        should_emit_guidance_reminder(
            guidance=decision,
            last_guidance_problem_id="problem-1",
            last_guidance_at="2026-03-18T12:10:00+00:00",
            now_iso="2026-03-18T12:20:00+00:00",
        )
        is False
    )
