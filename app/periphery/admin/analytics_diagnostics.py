"""Failure categorization helpers for the admin analytics report."""

from __future__ import annotations


def classify_operation_failure(
    *,
    command: str,
    error_stage: str | None,
    error_code: str | None,
    error_message: str | None,
) -> dict[str, str]:
    """Return one stable diagnosis payload for an operation failure."""

    message = (error_message or "").lower()
    if "uq_evidence_repo_ref" in message or "uq_evidence_repo_episode_event" in message:
        return _diagnosis(
            category="duplicate_evidence_ref",
            summary="Evidence refs are being inserted twice for the same repo/event pair.",
            recommended_action="Make evidence-ref writes idempotent before the insert path reaches the unique constraint.",
        )
    if "episode event not found" in message:
        return _diagnosis(
            category="missing_episode_event",
            summary="Writes are referencing episode events that are not visible or were not imported.",
            recommended_action="Tighten the events-before-write flow and validate that evidence refs come from the latest visible events call.",
        )
    if command == "events" and error_stage == "schema_validation":
        return _diagnosis(
            category="invalid_events_payload",
            summary="Agents are sending invalid payloads to events.",
            recommended_action="Improve examples and validation feedback for the events payload shape.",
        )
    if command == "update" and error_stage == "schema_validation":
        return _diagnosis(
            category="invalid_update_payload",
            summary="Agents are sending invalid update payloads.",
            recommended_action="Improve update examples and make utility-vote usage easier to follow correctly.",
        )
    if "no active host session found" in message:
        return _diagnosis(
            category="missing_active_host_session",
            summary="Shellbrain cannot resolve a live host session for the repo when events is requested.",
            recommended_action="Harden session discovery and clarify recovery steps when the host transcript is unavailable.",
        )
    if "operation not permitted" in message and "session_state" in message:
        return _diagnosis(
            category="session_state_permission_error",
            summary="Shellbrain hit a filesystem permission error while touching repo-local session state.",
            recommended_action="Harden session-state file writes and path handling under restricted environments.",
        )
    return _diagnosis(
        category="unknown",
        summary=_fallback_summary(error_stage=error_stage, error_code=error_code),
        recommended_action="Inspect the sample failures and add a dedicated diagnosis rule if this pattern is recurring.",
    )


def classify_sync_failure(*, error_stage: str | None, error_message: str | None) -> dict[str, str]:
    """Return one stable diagnosis payload for a sync failure."""

    message = (error_message or "").lower()
    if "episode_events_episode_id_seq_key" in message:
        return _diagnosis(
            category="duplicate_episode_event_seq",
            summary="Episode sync is re-importing events with a sequence number that already exists.",
            recommended_action="Make sync append logic idempotent for already-seen episode events and sequence assignment.",
        )
    if "operation not permitted" in message and "session_state" in message:
        return _diagnosis(
            category="session_state_permission_error",
            summary="Sync is blocked by a filesystem permission failure in repo-local session state.",
            recommended_action="Harden session-state file writes and path handling under restricted environments.",
        )
    return _diagnosis(
        category="unknown",
        summary=_fallback_summary(error_stage=error_stage, error_code=None),
        recommended_action="Inspect the sample sync failures and add a dedicated diagnosis rule if this pattern is recurring.",
    )


def _diagnosis(*, category: str, summary: str, recommended_action: str) -> dict[str, str]:
    """Build one diagnosis dictionary."""

    return {
        "category": category,
        "summary": summary,
        "recommended_action": recommended_action,
    }


def _fallback_summary(*, error_stage: str | None, error_code: str | None) -> str:
    """Build a compact fallback summary when no specific rule matched."""

    if error_stage and error_code:
        return f"Failure pattern not yet classified ({error_stage}/{error_code})."
    if error_stage:
        return f"Failure pattern not yet classified ({error_stage})."
    return "Failure pattern not yet classified."
