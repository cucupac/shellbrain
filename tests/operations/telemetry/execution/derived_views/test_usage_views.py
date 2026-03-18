"""Derived-view contracts for usage telemetry analytics."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.usefixtures("telemetry_db_reset")


def test_usage_command_daily_should_always_aggregate_daily_command_outcomes_from_operation_invocations(
    integration_engine,
    seed_usage_telemetry_dataset,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """usage_command_daily should always aggregate daily command outcomes from operation invocations."""

    seed_usage_telemetry_dataset()

    assert_relation_exists("usage_command_daily")
    rows = fetch_relation_rows(
        "usage_command_daily",
        where_sql="repo_id = :repo_id",
        params={"repo_id": "telemetry-repo"},
        order_by="command ASC",
    )

    assert [row["command"] for row in rows] == ["create", "events", "read"]
    assert [row["invocation_count"] for row in rows] == [1, 1, 1]


def test_usage_memory_retrieval_should_always_aggregate_retrieval_frequency_and_last_seen_timestamps_from_read_result_items(
    integration_engine,
    seed_usage_telemetry_dataset,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """usage_memory_retrieval should always aggregate retrieval frequency and last-seen timestamps from read result items."""

    seed_usage_telemetry_dataset()

    assert_relation_exists("usage_memory_retrieval")
    rows = fetch_relation_rows(
        "usage_memory_retrieval",
        where_sql="repo_id = :repo_id AND memory_id = :memory_id",
        params={"repo_id": "telemetry-repo", "memory_id": "mem-1"},
    )

    assert len(rows) == 1
    assert rows[0]["kind"] == "problem"
    assert rows[0]["section"] == "direct"
    assert rows[0]["retrieval_count"] == 1
    assert rows[0]["last_seen_at"] is not None


def test_usage_write_effects_should_always_aggregate_write_effect_types_and_counts_from_write_effect_items(
    integration_engine,
    seed_usage_telemetry_dataset,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """usage_write_effects should always aggregate write effect types and counts from write effect items."""

    seed_usage_telemetry_dataset()

    assert_relation_exists("usage_write_effects")
    rows = fetch_relation_rows(
        "usage_write_effects",
        where_sql="repo_id = :repo_id",
        params={"repo_id": "telemetry-repo"},
        order_by="effect_type ASC",
    )

    assert [row["effect_type"] for row in rows] == ["association_edge_created", "memory_created"]
    assert [row["effect_count"] for row in rows] == [1, 1]


def test_usage_sync_health_should_always_aggregate_sync_outcomes_and_tool_type_counts_by_host(
    integration_engine,
    seed_usage_telemetry_dataset,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """usage_sync_health should always aggregate sync outcomes and tool-type counts by host."""

    seed_usage_telemetry_dataset()

    assert_relation_exists("usage_sync_health")
    rows = fetch_relation_rows(
        "usage_sync_health",
        where_sql="repo_id = :repo_id AND host_app = :host_app",
        params={"repo_id": "telemetry-repo", "host_app": "codex"},
    )

    assert len(rows) == 1
    assert rows[0]["sync_run_count"] == 1
    assert rows[0]["failed_sync_count"] == 0
    assert rows[0]["imported_event_count"] == 3
    assert json.loads(rows[0]["tool_type_counts"] if isinstance(rows[0]["tool_type_counts"], str) else json.dumps(rows[0]["tool_type_counts"])) == {"exec_command": 1}


def test_usage_session_protocol_should_always_aggregate_per_thread_read_events_and_write_counts(
    integration_engine,
    seed_usage_telemetry_dataset,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """usage_session_protocol should always aggregate per-thread read, events, and write counts."""

    seed_usage_telemetry_dataset()

    assert_relation_exists("usage_session_protocol")
    rows = fetch_relation_rows(
        "usage_session_protocol",
        where_sql="repo_id = :repo_id AND selected_thread_id = :thread_id",
        params={"repo_id": "telemetry-repo", "thread_id": "codex:session-1"},
    )

    assert len(rows) == 1
    assert rows[0]["read_count"] == 1
    assert rows[0]["events_count"] == 1
    assert rows[0]["write_count"] == 1


def test_usage_session_protocol_should_always_aggregate_zero_result_reads_and_ambiguous_session_selections(
    integration_engine,
    seed_usage_telemetry_dataset,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """usage_session_protocol should always aggregate zero-result reads and ambiguous session selections."""

    seed_usage_telemetry_dataset()
    _seed_zero_result_read(integration_engine)

    assert_relation_exists("usage_session_protocol")
    rows = fetch_relation_rows(
        "usage_session_protocol",
        where_sql="repo_id = :repo_id AND selected_thread_id = :thread_id",
        params={"repo_id": "telemetry-repo", "thread_id": "codex:session-1"},
    )

    assert len(rows) == 1
    assert rows[0]["zero_result_read_count"] == 1
    assert rows[0]["ambiguous_selection_count"] == 1


def test_usage_session_protocol_should_always_aggregate_writes_preceded_by_events_and_events_followed_by_no_write(
    integration_engine,
    seed_usage_telemetry_dataset,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """usage_session_protocol should always aggregate writes preceded by events and events followed by no write."""

    seed_usage_telemetry_dataset()
    _seed_events_without_following_write(integration_engine)

    assert_relation_exists("usage_session_protocol")
    rows = fetch_relation_rows(
        "usage_session_protocol",
        where_sql="repo_id = :repo_id AND selected_thread_id = :thread_id",
        params={"repo_id": "telemetry-repo", "thread_id": "codex:session-1"},
    )

    assert len(rows) == 1
    assert rows[0]["writes_preceded_by_events_count"] == 1
    assert rows[0]["events_without_following_write_count"] == 1


def _seed_zero_result_read(integration_engine) -> None:
    """Insert one same-thread zero-result read invocation for view-aggregation tests."""

    with integration_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO operation_invocations (
                    id,
                    command,
                    repo_id,
                    repo_root,
                    no_sync,
                    selected_host_app,
                    selected_host_session_key,
                    selected_thread_id,
                    selected_episode_id,
                    matching_candidate_count,
                    selection_ambiguous,
                    outcome,
                    error_stage,
                    error_code,
                    error_message,
                    total_latency_ms,
                    poller_start_attempted,
                    poller_started,
                    created_at
                ) VALUES (
                    :id,
                    :command,
                    :repo_id,
                    :repo_root,
                    :no_sync,
                    :selected_host_app,
                    :selected_host_session_key,
                    :selected_thread_id,
                    :selected_episode_id,
                    :matching_candidate_count,
                    :selection_ambiguous,
                    :outcome,
                    :error_stage,
                    :error_code,
                    :error_message,
                    :total_latency_ms,
                    :poller_start_attempted,
                    :poller_started,
                    :created_at
                )
                """
            ),
            {
                "id": "inv-read-zero",
                "command": "read",
                "repo_id": "telemetry-repo",
                "repo_root": "/tmp/telemetry-repo",
                "no_sync": False,
                "selected_host_app": "codex",
                "selected_host_session_key": "session-1",
                "selected_thread_id": "codex:session-1",
                "selected_episode_id": "episode-1",
                "matching_candidate_count": 1,
                "selection_ambiguous": False,
                "outcome": "ok",
                "error_stage": None,
                "error_code": None,
                "error_message": None,
                "total_latency_ms": 8,
                "poller_start_attempted": False,
                "poller_started": False,
                "created_at": "2026-03-18T10:05:00+00:00",
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO read_invocation_summaries (
                    invocation_id,
                    query_text,
                    mode,
                    requested_limit,
                    effective_limit,
                    include_global,
                    kinds_filter,
                    direct_count,
                    explicit_related_count,
                    implicit_related_count,
                    total_returned,
                    zero_results
                ) VALUES (
                    :invocation_id,
                    :query_text,
                    :mode,
                    :requested_limit,
                    :effective_limit,
                    :include_global,
                    CAST(:kinds_filter AS JSONB),
                    :direct_count,
                    :explicit_related_count,
                    :implicit_related_count,
                    :total_returned,
                    :zero_results
                )
                """
            ),
            {
                "invocation_id": "inv-read-zero",
                "query_text": "no results",
                "mode": "targeted",
                "requested_limit": 8,
                "effective_limit": 8,
                "include_global": True,
                "kinds_filter": json.dumps(["problem"]),
                "direct_count": 0,
                "explicit_related_count": 0,
                "implicit_related_count": 0,
                "total_returned": 0,
                "zero_results": True,
            },
        )


def _seed_events_without_following_write(integration_engine) -> None:
    """Insert one later same-thread events invocation with no later write."""

    with integration_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO operation_invocations (
                    id,
                    command,
                    repo_id,
                    repo_root,
                    no_sync,
                    selected_host_app,
                    selected_host_session_key,
                    selected_thread_id,
                    selected_episode_id,
                    matching_candidate_count,
                    selection_ambiguous,
                    outcome,
                    error_stage,
                    error_code,
                    error_message,
                    total_latency_ms,
                    poller_start_attempted,
                    poller_started,
                    created_at
                ) VALUES (
                    :id,
                    :command,
                    :repo_id,
                    :repo_root,
                    :no_sync,
                    :selected_host_app,
                    :selected_host_session_key,
                    :selected_thread_id,
                    :selected_episode_id,
                    :matching_candidate_count,
                    :selection_ambiguous,
                    :outcome,
                    :error_stage,
                    :error_code,
                    :error_message,
                    :total_latency_ms,
                    :poller_start_attempted,
                    :poller_started,
                    :created_at
                )
                """
            ),
            {
                "id": "inv-events-no-write",
                "command": "events",
                "repo_id": "telemetry-repo",
                "repo_root": "/tmp/telemetry-repo",
                "no_sync": False,
                "selected_host_app": "codex",
                "selected_host_session_key": "session-1",
                "selected_thread_id": "codex:session-1",
                "selected_episode_id": "episode-1",
                "matching_candidate_count": 1,
                "selection_ambiguous": False,
                "outcome": "ok",
                "error_stage": None,
                "error_code": None,
                "error_message": None,
                "total_latency_ms": 7,
                "poller_start_attempted": False,
                "poller_started": False,
                "created_at": "2026-03-18T10:06:00+00:00",
            },
        )
