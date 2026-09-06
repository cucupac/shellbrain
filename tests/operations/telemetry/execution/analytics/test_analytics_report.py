"""Analytics reports persisted measurements without inventing product advice."""

from datetime import datetime, timedelta, timezone

import pytest

import app.startup.analytics as analytics_module
from app.core.use_cases.admin.generate_analytics_report import build_analytics_report
from app.infrastructure.db.runtime.models.telemetry import (
    episode_sync_runs,
    operation_invocations,
    read_invocation_summaries,
    recall_invocation_summaries,
)

pytestmark = pytest.mark.usefixtures("telemetry_db_reset")


def test_analytics_counts_read_recall_sync_and_errors(integration_engine, monkeypatch):
    end = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    start = end - timedelta(days=2)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return end

    monkeypatch.setattr(analytics_module, "datetime", FixedDateTime)
    with integration_engine.begin() as conn:
        for invocation_id, command, repo, outcome, created_at, latency in [
            ("read-ok", "read", "repo-a", "ok", start, 10),
            ("read-empty", "read", "repo-a", "ok", start, 30),
            ("recall-empty", "recall", "repo-b", "ok", start, 50),
            ("recall-ok", "recall", "repo-b", "ok", start, 70),
            ("write-error", "create", "repo-b", "error", start, 20),
            ("too-old", "read", "repo-a", "ok", start - timedelta(seconds=1), 999),
            ("too-new", "read", "repo-a", "ok", end, 999),
        ]:
            conn.execute(
                operation_invocations.insert().values(
                    id=invocation_id,
                    command=command,
                    repo_id=repo,
                    repo_root="/repo",
                    outcome=outcome,
                    total_latency_ms=latency,
                    created_at=created_at,
                    error_stage="execution" if outcome == "error" else None,
                    error_code="BAD_INPUT" if outcome == "error" else None,
                    error_message="Invalid evidence" if outcome == "error" else None,
                )
            )
        for invocation_id, empty in [("read-ok", False), ("read-empty", True)]:
            conn.execute(
                read_invocation_summaries.insert().values(
                    invocation_id=invocation_id,
                    query_text="deployment lesson",
                    mode="targeted",
                    requested_limit=8,
                    effective_limit=8,
                    include_global=True,
                    direct_count=0 if empty else 1,
                    explicit_related_count=0,
                    implicit_related_count=0,
                    total_returned=0 if empty else 1,
                    zero_results=empty,
                    created_at=start,
                )
            )
        for invocation_id, reason in [
            ("recall-empty", "no_candidates"),
            ("recall-ok", None),
        ]:
            conn.execute(
                recall_invocation_summaries.insert().values(
                    invocation_id=invocation_id,
                    query_text="deployment lesson",
                    candidate_token_estimate=0 if reason else 100,
                    brief_token_estimate=0 if reason else 25,
                    fallback_reason=reason,
                    created_at=start,
                )
            )
        for sync_id, outcome in [("sync-ok", "ok"), ("sync-error", "error")]:
            conn.execute(
                episode_sync_runs.insert().values(
                    id=sync_id,
                    source="events_inline",
                    repo_id="repo-b",
                    host_app="codex",
                    host_session_key="session",
                    thread_id="thread",
                    outcome=outcome,
                    duration_ms=10,
                    imported_event_count=3 if outcome == "ok" else 0,
                    created_at=start,
                    error_stage="parse" if outcome == "error" else None,
                    error_message="Malformed transcript"
                    if outcome == "error"
                    else None,
                )
            )

    report = analytics_module.build_analytics_report(engine=integration_engine, days=2)
    assert report["summary"] == {
        "repo_count": 2,
        "invocation_count": 5,
        "failure_count": 2,
        "sync_run_count": 2,
    }
    commands = {(row["repo_id"], row["command"]): row for row in report["commands"]}
    assert commands[("repo-a", "read")]["avg_latency_ms"] == 20
    assert commands[("repo-a", "read")]["max_latency_ms"] == 30
    assert report["retrieval"] == [
        {
            "repo_id": "repo-a",
            "request_count": 2,
            "zero_result_count": 1,
            "sample_empty_invocation_ids": ["read-empty"],
        },
        {
            "repo_id": "repo-b",
            "request_count": 2,
            "zero_result_count": 1,
            "sample_empty_invocation_ids": ["recall-empty"],
        },
    ]
    assert report["sync"][0]["imported_event_count"] == 3
    assert report["sync"][0]["failure_count"] == 1
    assert {row["error_message"] for row in report["failures"]} == {
        "Invalid evidence",
        "Malformed transcript",
    }
    assert {row["sample_record_ids"][0] for row in report["failures"]} == {
        "write-error",
        "sync-error",
    }
    assert set(report) == {
        "window",
        "summary",
        "commands",
        "retrieval",
        "sync",
        "failures",
    }


def test_empty_analytics_has_zero_counts():
    report = build_analytics_report(
        days=2,
        end_at=datetime(2026, 3, 24, tzinfo=timezone.utc),
        operation_rows=[],
        read_rows=[],
        sync_rows=[],
    )
    assert all(value == 0 for value in report["summary"].values())
    assert all(
        report[key] == [] for key in ("commands", "retrieval", "sync", "failures")
    )


@pytest.mark.parametrize("days", [0, -1])
def test_invalid_analytics_window_is_rejected(days):
    with pytest.raises(ValueError, match="greater than 0"):
        build_analytics_report(
            days=days,
            end_at=datetime(2026, 3, 24, tzinfo=timezone.utc),
            operation_rows=[],
            read_rows=[],
            sync_rows=[],
        )
