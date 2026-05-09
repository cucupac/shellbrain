"""Integration coverage for repo-scoped metrics snapshots."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.infrastructure.db.runtime.models.memories import memories
from app.infrastructure.db.runtime.models.telemetry import (
    episode_sync_runs,
    operation_invocations,
    read_invocation_summaries,
    write_invocation_summaries,
)
from app.infrastructure.db.runtime.models.utility import utility_observations
import app.startup.metrics as metrics_service


pytestmark = pytest.mark.usefixtures("telemetry_db_reset")


def test_build_metrics_snapshot_should_report_healthy_when_utility_improves(
    integration_engine,
    monkeypatch,
) -> None:
    """Healthy snapshots should show stronger utility and stable retrieval behavior."""

    fixed_now = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(metrics_service, "_REAL_DATETIME", _fixed_datetime(fixed_now))
    _seed_snapshot_dataset(
        integration_engine,
        fixed_now=fixed_now,
        repo_id="github.com/example/healthy",
        current_utility_votes=[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0],
        previous_utility_votes=[1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        current_opportunity_count=6,
        current_followthrough_count=5,
        previous_opportunity_count=6,
        previous_followthrough_count=4,
        current_read_count=20,
        current_zero_result_count=2,
        previous_read_count=20,
        previous_zero_result_count=3,
        current_write_count=20,
        current_compliant_count=18,
        previous_write_count=20,
        previous_compliant_count=16,
    )

    snapshot = metrics_service.build_metrics_snapshot(
        engine=integration_engine,
        repo_id="github.com/example/healthy",
        days=2,
    )
    metrics = {metric["name"]: metric for metric in snapshot["metrics"]}

    assert snapshot["status"] == "healthy"
    assert snapshot["confidence"] == "medium"
    assert snapshot["summary_md"].count(". ") == 2
    assert snapshot["summary_md"].endswith(".")
    assert metrics["Utility score trend"]["current"] == pytest.approx(0.6)
    assert metrics["Utility score trend"]["previous"] == pytest.approx(0.2)
    assert metrics["Utility follow-through"]["current"] == pytest.approx(5 / 6)
    assert metrics["Zero-result read rate"]["current"] == pytest.approx(0.1)
    assert metrics["Events-before-write compliance"]["current"] == pytest.approx(0.9)
    assert len(metrics["Utility score trend"]["daily_series"]) == 2


def test_build_metrics_snapshot_should_mark_slipping_when_utility_score_drops(
    integration_engine,
    monkeypatch,
) -> None:
    """A large utility-score drop should move the repo into slipping status."""

    fixed_now = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(metrics_service, "_REAL_DATETIME", _fixed_datetime(fixed_now))
    _seed_snapshot_dataset(
        integration_engine,
        fixed_now=fixed_now,
        repo_id="github.com/example/slipping-utility",
        current_utility_votes=[1.0] + [0.0] * 9,
        previous_utility_votes=[1.0, 1.0, 1.0, 1.0] + [0.0] * 6,
        current_opportunity_count=6,
        current_followthrough_count=5,
        previous_opportunity_count=6,
        previous_followthrough_count=5,
        current_read_count=20,
        current_zero_result_count=2,
        previous_read_count=20,
        previous_zero_result_count=2,
        current_write_count=20,
        current_compliant_count=18,
        previous_write_count=20,
        previous_compliant_count=18,
    )

    snapshot = metrics_service.build_metrics_snapshot(
        engine=integration_engine,
        repo_id="github.com/example/slipping-utility",
        days=2,
    )
    metrics = {metric["name"]: metric for metric in snapshot["metrics"]}

    assert snapshot["status"] == "slipping"
    assert metrics["Utility score trend"]["delta"] == pytest.approx(-0.3)


def test_build_metrics_snapshot_should_mark_insufficient_signal_when_votes_are_sparse(
    integration_engine,
    monkeypatch,
) -> None:
    """Thin utility and follow-through samples should suppress stronger health claims."""

    fixed_now = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(metrics_service, "_REAL_DATETIME", _fixed_datetime(fixed_now))
    _seed_snapshot_dataset(
        integration_engine,
        fixed_now=fixed_now,
        repo_id="github.com/example/thin-signal",
        current_utility_votes=[1.0] * 9,
        previous_utility_votes=[1.0] * 9,
        current_opportunity_count=4,
        current_followthrough_count=3,
        previous_opportunity_count=4,
        previous_followthrough_count=3,
        current_read_count=10,
        current_zero_result_count=1,
        previous_read_count=10,
        previous_zero_result_count=1,
        current_write_count=10,
        current_compliant_count=8,
        previous_write_count=10,
        previous_compliant_count=8,
    )

    snapshot = metrics_service.build_metrics_snapshot(
        engine=integration_engine,
        repo_id="github.com/example/thin-signal",
        days=2,
    )

    assert snapshot["status"] == "insufficient_signal"
    assert snapshot["confidence"] == "low"


def test_build_metrics_snapshot_should_mark_slipping_when_zero_result_reads_regress(
    integration_engine,
    monkeypatch,
) -> None:
    """A read-quality regression should move the snapshot into slipping status."""

    fixed_now = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(metrics_service, "_REAL_DATETIME", _fixed_datetime(fixed_now))
    _seed_snapshot_dataset(
        integration_engine,
        fixed_now=fixed_now,
        repo_id="github.com/example/slipping-reads",
        current_utility_votes=[1.0] * 6 + [0.0] * 4,
        previous_utility_votes=[1.0] * 5 + [0.0] * 5,
        current_opportunity_count=6,
        current_followthrough_count=5,
        previous_opportunity_count=6,
        previous_followthrough_count=5,
        current_read_count=20,
        current_zero_result_count=6,
        previous_read_count=20,
        previous_zero_result_count=2,
        current_write_count=20,
        current_compliant_count=18,
        previous_write_count=20,
        previous_compliant_count=18,
    )

    snapshot = metrics_service.build_metrics_snapshot(
        engine=integration_engine,
        repo_id="github.com/example/slipping-reads",
        days=2,
    )
    metrics = {metric["name"]: metric for metric in snapshot["metrics"]}

    assert snapshot["status"] == "slipping"
    assert metrics["Zero-result read rate"]["delta"] == pytest.approx(0.2)


def test_build_metrics_snapshot_should_track_events_before_write_regression_without_flipping_status(
    integration_engine,
    monkeypatch,
) -> None:
    """Compliance regressions should still show up even when headline status stays healthy."""

    fixed_now = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(metrics_service, "_REAL_DATETIME", _fixed_datetime(fixed_now))
    _seed_snapshot_dataset(
        integration_engine,
        fixed_now=fixed_now,
        repo_id="github.com/example/compliance-regression",
        current_utility_votes=[1.0] * 6 + [0.0] * 4,
        previous_utility_votes=[1.0] * 5 + [0.0] * 5,
        current_opportunity_count=6,
        current_followthrough_count=5,
        previous_opportunity_count=6,
        previous_followthrough_count=5,
        current_read_count=20,
        current_zero_result_count=2,
        previous_read_count=20,
        previous_zero_result_count=2,
        current_write_count=20,
        current_compliant_count=8,
        previous_write_count=20,
        previous_compliant_count=18,
    )

    snapshot = metrics_service.build_metrics_snapshot(
        engine=integration_engine,
        repo_id="github.com/example/compliance-regression",
        days=2,
    )
    metrics = {metric["name"]: metric for metric in snapshot["metrics"]}

    assert snapshot["status"] == "healthy"
    assert metrics["Events-before-write compliance"]["delta"] == pytest.approx(-0.5)


def test_build_metrics_snapshot_should_emit_sync_alerts_and_degrade_confidence(
    integration_engine,
    monkeypatch,
) -> None:
    """Sync instability should show up as a trust alert instead of a primary card."""

    fixed_now = datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(metrics_service, "_REAL_DATETIME", _fixed_datetime(fixed_now))
    _seed_snapshot_dataset(
        integration_engine,
        fixed_now=fixed_now,
        repo_id="github.com/example/sync-warning",
        current_utility_votes=[1.0] * 30,
        previous_utility_votes=[1.0] * 30,
        current_opportunity_count=20,
        current_followthrough_count=18,
        previous_opportunity_count=20,
        previous_followthrough_count=18,
        current_read_count=60,
        current_zero_result_count=5,
        previous_read_count=60,
        previous_zero_result_count=5,
        current_write_count=60,
        current_compliant_count=55,
        previous_write_count=60,
        previous_compliant_count=55,
        current_sync_run_count=20,
        current_sync_failure_count=2,
    )

    snapshot = metrics_service.build_metrics_snapshot(
        engine=integration_engine,
        repo_id="github.com/example/sync-warning",
        days=2,
    )

    assert snapshot["status"] == "healthy"
    assert snapshot["confidence"] == "medium"
    assert snapshot["alerts"] == [
        {
            "code": "sync_health_warning",
            "severity": "warning",
            "message": "Sync health is reducing confidence in the snapshot (2 failed sync runs out of 20).",
            "failure_rate": pytest.approx(0.1),
            "sync_run_count": 20,
            "failed_sync_count": 2,
        }
    ]


def _seed_snapshot_dataset(
    integration_engine,
    *,
    fixed_now: datetime,
    repo_id: str,
    current_utility_votes: list[float],
    previous_utility_votes: list[float],
    current_opportunity_count: int,
    current_followthrough_count: int,
    previous_opportunity_count: int,
    previous_followthrough_count: int,
    current_read_count: int,
    current_zero_result_count: int,
    previous_read_count: int,
    previous_zero_result_count: int,
    current_write_count: int,
    current_compliant_count: int,
    previous_write_count: int,
    previous_compliant_count: int,
    current_sync_run_count: int = 0,
    current_sync_failure_count: int = 0,
) -> None:
    """Insert one deterministic repo dataset that exercises the metrics snapshot."""

    assert current_read_count >= current_opportunity_count
    assert previous_read_count >= previous_opportunity_count
    assert current_write_count >= current_followthrough_count
    assert previous_write_count >= previous_followthrough_count
    assert current_compliant_count >= current_followthrough_count
    assert previous_compliant_count >= previous_followthrough_count
    assert current_zero_result_count <= current_read_count - current_opportunity_count
    assert (
        previous_zero_result_count <= previous_read_count - previous_opportunity_count
    )
    assert 0 <= current_sync_failure_count <= current_sync_run_count

    problem_id = f"{repo_id}-problem"
    memory_id = f"{repo_id}-memory"

    memory_rows = [
        _memory_row(
            memory_id=problem_id, repo_id=repo_id, kind="problem", text_value="Problem."
        ),
        _memory_row(
            memory_id=memory_id,
            repo_id=repo_id,
            kind="solution",
            text_value="Solution.",
        ),
    ]

    utility_rows: list[dict[str, object]] = []
    op_rows: list[dict[str, object]] = []
    read_rows: list[dict[str, object]] = []
    write_rows: list[dict[str, object]] = []
    sync_rows: list[dict[str, object]] = []

    current_utility_start = fixed_now - timedelta(days=1, hours=11)
    previous_utility_start = fixed_now - timedelta(days=2, hours=23)
    for index, vote in enumerate(previous_utility_votes):
        utility_rows.append(
            _utility_row(
                observation_id=f"prev-utility-{index + 1}",
                memory_id=memory_id,
                problem_id=problem_id,
                vote=vote,
                created_at=previous_utility_start + timedelta(minutes=index),
            )
        )
    for index, vote in enumerate(current_utility_votes):
        utility_rows.append(
            _utility_row(
                observation_id=f"cur-utility-{index + 1}",
                memory_id=memory_id,
                problem_id=problem_id,
                vote=vote,
                created_at=current_utility_start + timedelta(minutes=index),
            )
        )

    previous_read_start = fixed_now - timedelta(days=2, hours=22)
    current_read_start = fixed_now - timedelta(days=1, hours=10)
    _append_followthrough_rows(
        op_rows=op_rows,
        read_rows=read_rows,
        write_rows=write_rows,
        repo_id=repo_id,
        phase="prev",
        base_time=previous_read_start,
        opportunity_count=previous_opportunity_count,
        followthrough_count=previous_followthrough_count,
    )
    _append_followthrough_rows(
        op_rows=op_rows,
        read_rows=read_rows,
        write_rows=write_rows,
        repo_id=repo_id,
        phase="cur",
        base_time=current_read_start,
        opportunity_count=current_opportunity_count,
        followthrough_count=current_followthrough_count,
    )

    _append_extra_reads(
        op_rows=op_rows,
        read_rows=read_rows,
        repo_id=repo_id,
        phase="prev",
        base_time=previous_read_start + timedelta(hours=2),
        extra_read_count=previous_read_count - previous_opportunity_count,
        zero_result_count=previous_zero_result_count,
    )
    _append_extra_reads(
        op_rows=op_rows,
        read_rows=read_rows,
        repo_id=repo_id,
        phase="cur",
        base_time=current_read_start + timedelta(hours=2),
        extra_read_count=current_read_count - current_opportunity_count,
        zero_result_count=current_zero_result_count,
    )

    previous_write_start = fixed_now - timedelta(days=2, hours=4)
    current_write_start = fixed_now - timedelta(hours=4)
    _append_extra_writes(
        op_rows=op_rows,
        write_rows=write_rows,
        repo_id=repo_id,
        phase="prev",
        base_time=previous_write_start,
        extra_write_count=previous_write_count - previous_followthrough_count,
        extra_compliant_count=previous_compliant_count - previous_followthrough_count,
    )
    _append_extra_writes(
        op_rows=op_rows,
        write_rows=write_rows,
        repo_id=repo_id,
        phase="cur",
        base_time=current_write_start,
        extra_write_count=current_write_count - current_followthrough_count,
        extra_compliant_count=current_compliant_count - current_followthrough_count,
    )

    current_sync_start = fixed_now - timedelta(hours=3)
    for index in range(current_sync_run_count):
        outcome = "error" if index < current_sync_failure_count else "ok"
        sync_rows.append(
            _sync_row(
                sync_run_id=f"cur-sync-{index + 1}",
                repo_id=repo_id,
                thread_id=f"codex:cur-sync-{index + 1}",
                outcome=outcome,
                created_at=current_sync_start + timedelta(minutes=index),
            )
        )

    with integration_engine.begin() as conn:
        conn.execute(memories.insert(), memory_rows)
        if utility_rows:
            conn.execute(utility_observations.insert(), utility_rows)
        if op_rows:
            conn.execute(operation_invocations.insert(), op_rows)
        if read_rows:
            conn.execute(read_invocation_summaries.insert(), read_rows)
        if write_rows:
            conn.execute(write_invocation_summaries.insert(), write_rows)
        if sync_rows:
            conn.execute(episode_sync_runs.insert(), sync_rows)


def _append_followthrough_rows(
    *,
    op_rows: list[dict[str, object]],
    read_rows: list[dict[str, object]],
    write_rows: list[dict[str, object]],
    repo_id: str,
    phase: str,
    base_time: datetime,
    opportunity_count: int,
    followthrough_count: int,
) -> None:
    """Append pending-utility guidance reads and any later utility-vote writes."""

    for index in range(opportunity_count):
        guidance_at = base_time + timedelta(minutes=index)
        thread_id = f"codex:{phase}-follow-{index + 1}"
        guidance_id = f"{phase}-guidance-{index + 1}"
        op_rows.append(
            _operation_row(
                invocation_id=guidance_id,
                command="read",
                repo_id=repo_id,
                thread_id=thread_id,
                created_at=guidance_at,
                guidance_codes=["pending_utility_votes"],
            )
        )
        read_rows.append(
            _read_summary_row(
                invocation_id=guidance_id,
                zero_results=False,
                created_at=guidance_at,
                query_text=f"{phase} guidance read",
            )
        )
        if index >= followthrough_count:
            continue
        event_id = f"{phase}-follow-events-{index + 1}"
        vote_id = f"{phase}-follow-vote-{index + 1}"
        event_at = guidance_at + timedelta(minutes=1)
        vote_at = guidance_at + timedelta(minutes=2)
        op_rows.append(
            _operation_row(
                invocation_id=event_id,
                command="events",
                repo_id=repo_id,
                thread_id=thread_id,
                created_at=event_at,
            )
        )
        op_rows.append(
            _operation_row(
                invocation_id=vote_id,
                command="update",
                repo_id=repo_id,
                thread_id=thread_id,
                created_at=vote_at,
            )
        )
        write_rows.append(
            _write_summary_row(
                invocation_id=vote_id,
                operation_command="update",
                target_memory_id=f"{phase}-vote-target-{index + 1}",
                update_type="utility_vote_batch",
                created_at=vote_at,
            )
        )


def _append_extra_reads(
    *,
    op_rows: list[dict[str, object]],
    read_rows: list[dict[str, object]],
    repo_id: str,
    phase: str,
    base_time: datetime,
    extra_read_count: int,
    zero_result_count: int,
) -> None:
    """Append non-guidance read invocations for read-rate metrics."""

    for index in range(extra_read_count):
        invocation_id = f"{phase}-extra-read-{index + 1}"
        created_at = base_time + timedelta(minutes=index)
        zero_results = index < zero_result_count
        op_rows.append(
            _operation_row(
                invocation_id=invocation_id,
                command="read",
                repo_id=repo_id,
                thread_id=f"codex:{phase}-extra-read-{index + 1}",
                created_at=created_at,
            )
        )
        read_rows.append(
            _read_summary_row(
                invocation_id=invocation_id,
                zero_results=zero_results,
                created_at=created_at,
                query_text=f"{phase} extra read",
            )
        )


def _append_extra_writes(
    *,
    op_rows: list[dict[str, object]],
    write_rows: list[dict[str, object]],
    repo_id: str,
    phase: str,
    base_time: datetime,
    extra_write_count: int,
    extra_compliant_count: int,
) -> None:
    """Append create writes, some with explicit prior events for compliance tracking."""

    for index in range(extra_write_count):
        created_at = base_time + timedelta(minutes=index)
        thread_id = f"codex:{phase}-extra-write-{index + 1}"
        if index < extra_compliant_count:
            op_rows.append(
                _operation_row(
                    invocation_id=f"{phase}-extra-write-events-{index + 1}",
                    command="events",
                    repo_id=repo_id,
                    thread_id=thread_id,
                    created_at=created_at - timedelta(seconds=30),
                )
            )
        invocation_id = f"{phase}-extra-write-{index + 1}"
        op_rows.append(
            _operation_row(
                invocation_id=invocation_id,
                command="create",
                repo_id=repo_id,
                thread_id=thread_id,
                created_at=created_at,
            )
        )
        write_rows.append(
            _write_summary_row(
                invocation_id=invocation_id,
                operation_command="create",
                target_memory_id=f"{phase}-extra-target-{index + 1}",
                update_type=None,
                created_at=created_at,
            )
        )


def _memory_row(
    *, memory_id: str, repo_id: str, kind: str, text_value: str
) -> dict[str, object]:
    """Return one minimal memories row for metrics integration tests."""

    return {
        "id": memory_id,
        "repo_id": repo_id,
        "scope": "repo",
        "kind": kind,
        "text": text_value,
        "created_at": datetime.now(timezone.utc),
        "archived": False,
    }


def _utility_row(
    *,
    observation_id: str,
    memory_id: str,
    problem_id: str,
    vote: float,
    created_at: datetime,
) -> dict[str, object]:
    """Return one utility observation row."""

    return {
        "id": observation_id,
        "memory_id": memory_id,
        "problem_id": problem_id,
        "vote": vote,
        "rationale": None,
        "created_at": created_at,
    }


def _operation_row(
    *,
    invocation_id: str,
    command: str,
    repo_id: str,
    thread_id: str,
    created_at: datetime,
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
        "selection_ambiguous": False,
        "outcome": "ok",
        "error_stage": None,
        "error_code": None,
        "error_message": None,
        "total_latency_ms": 25,
        "poller_start_attempted": False,
        "poller_started": False,
        "guidance_codes": guidance_codes or [],
        "created_at": created_at,
    }


def _read_summary_row(
    *, invocation_id: str, zero_results: bool, created_at: datetime, query_text: str
) -> dict[str, object]:
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
        "utility_observation_count": 1
        if update_type in {"utility_vote", "utility_vote_batch"}
        else 0,
        "association_effect_count": 0,
        "fact_update_count": 0,
        "created_at": created_at,
    }


def _sync_row(
    *,
    sync_run_id: str,
    repo_id: str,
    thread_id: str,
    outcome: str,
    created_at: datetime,
) -> dict[str, object]:
    """Return one episode_sync_runs row."""

    return {
        "id": sync_run_id,
        "source": "events_inline",
        "invocation_id": None,
        "repo_id": repo_id,
        "host_app": "codex",
        "host_session_key": thread_id.split(":", 1)[-1],
        "thread_id": thread_id,
        "episode_id": f"episode-{thread_id.split(':', 1)[-1]}",
        "transcript_path": None,
        "outcome": outcome,
        "error_stage": "sync" if outcome == "error" else None,
        "error_message": "sync failed" if outcome == "error" else None,
        "duration_ms": 10,
        "imported_event_count": 1 if outcome == "ok" else 0,
        "total_event_count": 1,
        "user_event_count": 1,
        "assistant_event_count": 0,
        "tool_event_count": 0,
        "system_event_count": 0,
        "created_at": created_at,
    }


def _fixed_datetime(fixed_now: datetime):
    """Return one datetime subclass whose now() stays pinned for snapshot tests."""

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is not None else fixed_now.replace(tzinfo=None)

    return _FixedDateTime
