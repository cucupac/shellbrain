"""Integration coverage for the admin analytics report."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import app.startup.analytics as analytics_module
from app.infrastructure.db.models.telemetry import (
    episode_sync_runs,
    operation_invocations,
    read_invocation_summaries,
    write_invocation_summaries,
)


pytestmark = pytest.mark.usefixtures("telemetry_db_reset")


def test_build_analytics_report_should_summarize_cross_repo_strengths_failures_and_gaps(
    integration_engine,
    monkeypatch,
) -> None:
    """The analytics report should answer the core reviewer-agent questions across repos."""

    fixed_now = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is not None else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(analytics_module, "datetime", _FixedDateTime)
    _seed_analytics_dataset(integration_engine, fixed_now=fixed_now)

    report = analytics_module.build_analytics_report(engine=integration_engine, days=2)

    assert report["window"]["days"] == 2
    assert report["summary"]["overall_health"] == "needs_attention"
    assert report["summary"]["repo_count"] == 2
    assert report["summary"]["failure_count"] == 8

    strength_categories = {item["category"] for item in report["strengths"]}
    failure_categories = {item["category"] for item in report["failures"]}
    gap_categories = {item["category"] for item in report["capability_gaps"]}
    priority_categories = {item["category"] for item in report["priorities"]}

    assert "command_success" in strength_categories
    assert "sync_stability" in strength_categories
    assert "events_before_write" in strength_categories

    assert "duplicate_evidence_ref" in failure_categories
    assert "duplicate_episode_event_seq" in failure_categories
    assert "zero_result_reads" in failure_categories
    assert "ambiguous_session_selection" in failure_categories

    assert "utility_vote_followthrough" in gap_categories
    assert "events_before_write" in gap_categories

    assert priority_categories & {"duplicate_evidence_ref", "duplicate_episode_event_seq", "events_before_write", "utility_vote_followthrough"}

    rollups = {row["repo_id"]: row for row in report["repo_rollups"]}
    assert rollups["github.com/example/good"]["strength_ids"]
    assert rollups["github.com/example/good"]["failure_count"] == 0
    assert rollups["github.com/example/bad"]["failure_ids"]
    assert rollups["github.com/example/bad"]["failure_count"] == 8
    assert rollups["github.com/example/bad"]["capability_gap_ids"]

    utility_gap = next(item for item in report["capability_gaps"] if item["category"] == "utility_vote_followthrough")
    assert utility_gap["metrics"]["opportunity_count"] == 2
    assert utility_gap["metrics"]["gap_count"] == 1


def _seed_analytics_dataset(integration_engine, *, fixed_now: datetime) -> None:
    """Insert one deterministic multi-repo telemetry dataset for analytics coverage."""

    repo_good = "github.com/example/good"
    repo_bad = "github.com/example/bad"
    base_time = fixed_now - timedelta(hours=12)

    op_rows: list[dict[str, object]] = []
    read_summary_rows: list[dict[str, object]] = []
    write_summary_rows: list[dict[str, object]] = []
    sync_rows: list[dict[str, object]] = []

    for index in range(10):
        invocation_id = f"good-read-{index + 1}"
        created_at = base_time + timedelta(minutes=index)
        op_rows.append(
            _operation_row(
                invocation_id=invocation_id,
                command="read",
                repo_id=repo_good,
                thread_id=f"codex:good-read-{index + 1}",
                created_at=created_at,
            )
        )
        read_summary_rows.append(_read_summary_row(invocation_id=invocation_id, zero_results=False, created_at=created_at, query_text="good read"))

    for index in range(5):
        thread_id = f"codex:good-write-{index + 1}"
        event_time = base_time + timedelta(hours=1, minutes=index)
        create_time = event_time + timedelta(seconds=15)
        event_id = f"good-event-{index + 1}"
        create_id = f"good-create-{index + 1}"
        op_rows.append(
            _operation_row(
                invocation_id=event_id,
                command="events",
                repo_id=repo_good,
                thread_id=thread_id,
                created_at=event_time,
            )
        )
        op_rows.append(
            _operation_row(
                invocation_id=create_id,
                command="create",
                repo_id=repo_good,
                thread_id=thread_id,
                created_at=create_time,
            )
        )
        write_summary_rows.append(
            _write_summary_row(
                invocation_id=create_id,
                operation_command="create",
                target_memory_id=f"good-memory-{index + 1}",
                update_type=None,
                created_at=create_time,
            )
        )

    for index in range(100):
        sync_rows.append(
            _sync_row(
                sync_run_id=f"good-sync-{index + 1}",
                repo_id=repo_good,
                host_app="codex",
                thread_id=f"codex:good-sync-{index + 1}",
                outcome="ok",
                created_at=base_time + timedelta(hours=2, seconds=index),
                error_stage=None,
                error_message=None,
            )
        )

    duplicate_message = 'duplicate key value violates unique constraint "uq_evidence_repo_ref"'
    for index in range(3):
        op_rows.append(
            _operation_row(
                invocation_id=f"bad-create-error-{index + 1}",
                command="create",
                repo_id=repo_bad,
                thread_id=f"codex:bad-create-{index + 1}",
                created_at=base_time + timedelta(hours=3, minutes=index),
                outcome="error",
                error_stage="internal_error",
                error_code="internal_error",
                error_message=duplicate_message,
            )
        )

    for index in range(5):
        invocation_id = f"bad-read-{index + 1}"
        created_at = base_time + timedelta(hours=4, minutes=index)
        op_rows.append(
            _operation_row(
                invocation_id=invocation_id,
                command="read",
                repo_id=repo_bad,
                thread_id=f"codex:bad-read-{index + 1}",
                created_at=created_at,
                selection_ambiguous=index < 3,
            )
        )
        read_summary_rows.append(
            _read_summary_row(
                invocation_id=invocation_id,
                zero_results=index < 2,
                created_at=created_at,
                query_text="bad read",
            )
        )

    op_rows.append(
        _operation_row(
            invocation_id="bad-guidance-gap",
            command="read",
            repo_id=repo_bad,
            thread_id="codex:bad-gap-1",
            created_at=base_time + timedelta(hours=5),
            guidance_codes=["pending_utility_votes"],
        )
    )
    read_summary_rows.append(
        _read_summary_row(
            invocation_id="bad-guidance-gap",
            zero_results=False,
            created_at=base_time + timedelta(hours=5),
            query_text="gap guidance",
        )
    )
    op_rows.append(
        _operation_row(
            invocation_id="bad-guidance-followthrough",
            command="read",
            repo_id=repo_bad,
            thread_id="codex:bad-gap-2",
            created_at=base_time + timedelta(hours=5, minutes=10),
            guidance_codes=["pending_utility_votes"],
        )
    )
    read_summary_rows.append(
        _read_summary_row(
            invocation_id="bad-guidance-followthrough",
            zero_results=False,
            created_at=base_time + timedelta(hours=5, minutes=10),
            query_text="followthrough guidance",
        )
    )
    op_rows.append(
        _operation_row(
            invocation_id="bad-utility-vote",
            command="update",
            repo_id=repo_bad,
            thread_id="codex:bad-gap-2",
            created_at=base_time + timedelta(hours=5, minutes=15),
        )
    )
    write_summary_rows.append(
        _write_summary_row(
            invocation_id="bad-utility-vote",
            operation_command="update",
            target_memory_id="problem-bad",
            update_type="utility_vote_batch",
            created_at=base_time + timedelta(hours=5, minutes=15),
        )
    )

    for index in range(2):
        invocation_id = f"bad-write-gap-{index + 1}"
        created_at = base_time + timedelta(hours=6, minutes=index)
        op_rows.append(
            _operation_row(
                invocation_id=invocation_id,
                command="create",
                repo_id=repo_bad,
                thread_id=f"codex:bad-write-gap-{index + 1}",
                created_at=created_at,
            )
        )
        write_summary_rows.append(
            _write_summary_row(
                invocation_id=invocation_id,
                operation_command="create",
                target_memory_id=f"bad-memory-{index + 1}",
                update_type=None,
                created_at=created_at,
            )
        )

    duplicate_seq_message = 'duplicate key value violates unique constraint "episode_events_episode_id_seq_key"'
    for index in range(5):
        sync_rows.append(
            _sync_row(
                sync_run_id=f"bad-sync-error-{index + 1}",
                repo_id=repo_bad,
                host_app="codex",
                thread_id=f"codex:bad-sync-{index + 1}",
                outcome="error",
                created_at=base_time + timedelta(hours=7, minutes=index),
                error_stage="sync",
                error_message=duplicate_seq_message,
            )
        )

    with integration_engine.begin() as conn:
        conn.execute(operation_invocations.insert(), op_rows)
        conn.execute(read_invocation_summaries.insert(), read_summary_rows)
        conn.execute(write_invocation_summaries.insert(), write_summary_rows)
        conn.execute(episode_sync_runs.insert(), sync_rows)


def _operation_row(
    *,
    invocation_id: str,
    command: str,
    repo_id: str,
    thread_id: str,
    created_at: datetime,
    outcome: str = "ok",
    error_stage: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    selection_ambiguous: bool = False,
    guidance_codes: list[str] | None = None,
) -> dict[str, object]:
    """Return one operation_invocations row."""

    return {
        "id": invocation_id,
        "command": command,
        "repo_id": repo_id,
        "repo_root": f"/tmp/{repo_id.rsplit('/', 1)[-1]}",
        "no_sync": False,
        "selected_host_app": "codex",
        "selected_host_session_key": thread_id.split(":", 1)[-1],
        "selected_thread_id": thread_id,
        "selected_episode_id": f"episode-{thread_id.split(':', 1)[-1]}",
        "matching_candidate_count": 0,
        "selection_ambiguous": selection_ambiguous,
        "outcome": outcome,
        "error_stage": error_stage,
        "error_code": error_code,
        "error_message": error_message,
        "total_latency_ms": 25,
        "poller_start_attempted": False,
        "poller_started": False,
        "guidance_codes": guidance_codes or [],
        "created_at": created_at,
    }


def _read_summary_row(*, invocation_id: str, zero_results: bool, created_at: datetime, query_text: str) -> dict[str, object]:
    """Return one read_invocation_summaries row."""

    return {
        "invocation_id": invocation_id,
        "query_text": query_text,
        "mode": "targeted",
        "requested_limit": 5,
        "effective_limit": 5,
        "include_global": True,
        "kinds_filter": None,
        "direct_count": 0 if zero_results else 1,
        "explicit_related_count": 0,
        "implicit_related_count": 0,
        "total_returned": 0 if zero_results else 1,
        "zero_results": zero_results,
        "created_at": created_at,
    }


def _write_summary_row(
    *,
    invocation_id: str,
    operation_command: str,
    target_memory_id: str,
    update_type: str | None,
    created_at: datetime,
) -> dict[str, object]:
    """Return one write_invocation_summaries row."""

    return {
        "invocation_id": invocation_id,
        "operation_command": operation_command,
        "target_memory_id": target_memory_id,
        "target_kind": "problem" if operation_command == "create" else None,
        "update_type": update_type,
        "scope": "repo" if operation_command == "create" else None,
        "evidence_ref_count": 1,
        "planned_effect_count": 1,
        "created_memory_count": 1 if operation_command == "create" else 0,
        "archived_memory_count": 0,
        "utility_observation_count": 1 if update_type in {"utility_vote", "utility_vote_batch"} else 0,
        "association_effect_count": 0,
        "fact_update_count": 0,
        "created_at": created_at,
    }


def _sync_row(
    *,
    sync_run_id: str,
    repo_id: str,
    host_app: str,
    thread_id: str,
    outcome: str,
    created_at: datetime,
    error_stage: str | None,
    error_message: str | None,
) -> dict[str, object]:
    """Return one episode_sync_runs row."""

    return {
        "id": sync_run_id,
        "source": "events_inline",
        "invocation_id": None,
        "repo_id": repo_id,
        "host_app": host_app,
        "host_session_key": thread_id.split(":", 1)[-1],
        "thread_id": thread_id,
        "episode_id": f"episode-{thread_id.split(':', 1)[-1]}",
        "transcript_path": None,
        "outcome": outcome,
        "error_stage": error_stage,
        "error_message": error_message,
        "duration_ms": 10,
        "imported_event_count": 1 if outcome == "ok" else 0,
        "total_event_count": 1,
        "user_event_count": 1,
        "assistant_event_count": 0,
        "tool_event_count": 0,
        "system_event_count": 0,
        "created_at": created_at,
    }
