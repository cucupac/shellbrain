"""Core guidance rules derived from trusted session state and telemetry."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from shellbrain.core.entities.guidance import GuidanceDecision
from shellbrain.core.entities.identity import CallerIdentity, IdentityTrustLevel
from shellbrain.core.entities.session_state import SessionState
from shellbrain.core.interfaces.repos import ITelemetryRepo


GUIDANCE_REMINDER_INTERVAL = timedelta(minutes=30)


def should_emit_guidance_reminder(
    *,
    guidance: GuidanceDecision,
    last_guidance_problem_id: str | None,
    last_guidance_at: str | None,
    now_iso: str,
) -> bool:
    """Return whether one reminder should be emitted for the current active problem."""

    if guidance.problem_id is None:
        return True
    if last_guidance_problem_id != guidance.problem_id or last_guidance_at is None:
        return True
    last_seen = _parse_iso(last_guidance_at)
    now = _parse_iso(now_iso)
    return now - last_seen >= GUIDANCE_REMINDER_INTERVAL


def build_pending_utility_guidance(
    *,
    repo_id: str,
    caller_identity: CallerIdentity | None,
    session_state: SessionState | None,
    telemetry: ITelemetryRepo,
    now_iso: str,
    strong: bool = False,
) -> list[GuidanceDecision]:
    """Build pending utility-vote guidance for one trusted caller and active problem."""

    if caller_identity is None or caller_identity.trust_level != IdentityTrustLevel.TRUSTED:
        return []
    if session_state is None or session_state.current_problem_id is None:
        return []

    candidates = telemetry.list_pending_utility_candidates(
        repo_id=repo_id,
        caller_id=caller_identity.canonical_id or "",
        problem_id=session_state.current_problem_id,
        since_iso=session_state.session_started_at,
    )
    if not candidates:
        return []

    decision = GuidanceDecision(
        code="pending_utility_votes",
        severity="info",
        message=f"{len(candidates)} retrieved memories still need utility votes for the active problem.",
        problem_id=session_state.current_problem_id,
        memory_ids=[candidate.memory_id for candidate in candidates],
        vote_scale_hint={"helpful": 1.0, "neutral": 0.0, "misleading": -1.0},
    )
    if strong:
        return [decision]
    if should_emit_guidance_reminder(
        guidance=decision,
        last_guidance_problem_id=session_state.last_guidance_problem_id,
        last_guidance_at=session_state.last_guidance_at,
        now_iso=now_iso,
    ):
        return [decision]
    return []


def _parse_iso(value: str) -> datetime:
    """Parse one ISO timestamp into a timezone-aware datetime."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
