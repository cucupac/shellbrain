"""Unit coverage for analytics failure classification."""

from __future__ import annotations

from app.periphery.admin.analytics_diagnostics import classify_operation_failure, classify_sync_failure


def test_operation_failure_classification_should_cover_known_categories() -> None:
    """Operation failures should map recurring patterns into stable diagnosis categories."""

    assert classify_operation_failure(
        command="create",
        error_stage="internal_error",
        error_code="internal_error",
        error_message='duplicate key value violates unique constraint "uq_evidence_repo_ref"',
    )["category"] == "duplicate_evidence_ref"
    assert classify_operation_failure(
        command="create",
        error_stage="internal_error",
        error_code="internal_error",
        error_message='duplicate key value violates unique constraint "uq_evidence_repo_episode_event"',
    )["category"] == "duplicate_evidence_ref"
    assert classify_operation_failure(
        command="create",
        error_stage="semantic_validation",
        error_code="not_found",
        error_message="Episode event not found: evt-123",
    )["category"] == "missing_episode_event"
    assert classify_operation_failure(
        command="events",
        error_stage="schema_validation",
        error_code="schema_error",
        error_message="Input should be less than or equal to 100",
    )["category"] == "invalid_events_payload"
    assert classify_operation_failure(
        command="update",
        error_stage="schema_validation",
        error_code="schema_error",
        error_message="Input should be 'utility_vote'",
    )["category"] == "invalid_update_payload"
    assert classify_operation_failure(
        command="events",
        error_stage="session_selection",
        error_code="not_found",
        error_message="No active host session found for this repo",
    )["category"] == "missing_active_host_session"
    assert classify_operation_failure(
        command="events",
        error_stage="sync",
        error_code="internal_error",
        error_message="Operation not permitted: '/tmp/repo/.shellbrain/session_state/codex/tmp123'",
    )["category"] == "session_state_permission_error"


def test_sync_failure_classification_should_cover_known_categories() -> None:
    """Sync failures should map recurring patterns into stable diagnosis categories."""

    assert classify_sync_failure(
        error_stage="sync",
        error_message='duplicate key value violates unique constraint "episode_events_episode_id_seq_key"',
    )["category"] == "duplicate_episode_event_seq"
    assert classify_sync_failure(
        error_stage="sync",
        error_message="Operation not permitted: '/tmp/repo/.shellbrain/session_state/codex/tmp123'",
    )["category"] == "session_state_permission_error"
    assert classify_sync_failure(
        error_stage="sync",
        error_message="something else happened",
    )["category"] == "unknown"
