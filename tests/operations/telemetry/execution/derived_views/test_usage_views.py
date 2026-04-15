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


def test_usage_session_tokens_should_prefer_exact_rows_when_nonzero_exact_data_exists(
    integration_engine,
    seed_usage_telemetry_dataset,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """usage_session_tokens should aggregate preferred per-session token totals from model_usage."""

    seed_usage_telemetry_dataset()
    with integration_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO model_usage (
                    id,
                    repo_id,
                    thread_id,
                    episode_id,
                    host_app,
                    host_session_key,
                    host_usage_key,
                    source_kind,
                    occurred_at,
                    agent_role,
                    provider,
                    model_id,
                    input_tokens,
                    output_tokens,
                    reasoning_output_tokens,
                    cached_input_tokens_total,
                    cache_read_input_tokens,
                    cache_creation_input_tokens,
                    capture_quality,
                    raw_usage_json
                ) VALUES
                  (
                    'usage-exact-1',
                    'telemetry-repo',
                    'codex:session-1',
                    'episode-1',
                    'codex',
                    'session-1',
                    'token-1',
                    'codex_transcript',
                    '2026-03-18T10:00:30+00:00',
                    'foreground',
                    'openai',
                    NULL,
                    100,
                    40,
                    10,
                    20,
                    0,
                    0,
                    'exact',
                    '{}'::jsonb
                  ),
                  (
                    'usage-estimated-1',
                    'telemetry-repo',
                    'codex:session-1',
                    'episode-1',
                    'codex',
                    'session-1',
                    'token-est-1',
                    'cursor_statusline_sidecar',
                    '2026-03-18T10:00:35+00:00',
                    'foreground',
                    'openai',
                    NULL,
                    5,
                    5,
                    0,
                    0,
                    0,
                    0,
                    'estimated',
                    '{}'::jsonb
                  )
                """
            )
        )

    assert_relation_exists("usage_session_tokens")
    rows = fetch_relation_rows(
        "usage_session_tokens",
        where_sql="repo_id = :repo_id AND host_app = :host_app AND host_session_key = :host_session_key",
        params={"repo_id": "telemetry-repo", "host_app": "codex", "host_session_key": "session-1"},
    )

    assert len(rows) == 1
    assert rows[0]["fresh_work_tokens"] == 140
    assert rows[0]["all_tokens_including_cache"] == 160
    assert rows[0]["reasoning_output_tokens"] == 10
    assert rows[0]["uses_exact_rows"] is True
    assert rows[0]["uses_estimated_rows"] is False


def test_usage_session_tokens_should_fall_back_to_estimated_rows_when_exact_cursor_rows_are_zero_only(
    integration_engine,
    seed_usage_telemetry_dataset,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """usage_session_tokens should prefer estimated rows over zero-only exact Cursor rows."""

    seed_usage_telemetry_dataset()
    with integration_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO episode_sync_runs (
                    id,
                    source,
                    invocation_id,
                    repo_id,
                    host_app,
                    host_session_key,
                    thread_id,
                    episode_id,
                    transcript_path,
                    outcome,
                    error_stage,
                    error_message,
                    duration_ms,
                    imported_event_count,
                    total_event_count,
                    user_event_count,
                    assistant_event_count,
                    tool_event_count,
                    system_event_count
                ) VALUES (
                    'sync-cursor-1',
                    'poller',
                    NULL,
                    'telemetry-repo',
                    'cursor',
                    'cursor-session-1',
                    'cursor:cursor-session-1',
                    'episode-2',
                    '/tmp/cursor/state.vscdb',
                    'ok',
                    NULL,
                    NULL,
                    10,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO model_usage (
                    id,
                    repo_id,
                    thread_id,
                    episode_id,
                    host_app,
                    host_session_key,
                    host_usage_key,
                    source_kind,
                    occurred_at,
                    agent_role,
                    provider,
                    model_id,
                    input_tokens,
                    output_tokens,
                    reasoning_output_tokens,
                    cached_input_tokens_total,
                    cache_read_input_tokens,
                    cache_creation_input_tokens,
                    capture_quality,
                    raw_usage_json
                ) VALUES
                  (
                    'cursor-exact-zero',
                    'telemetry-repo',
                    'cursor:cursor-session-1',
                    'episode-2',
                    'cursor',
                    'cursor-session-1',
                    'bubble-1',
                    'cursor_state_vscdb',
                    '2026-03-18T10:10:00+00:00',
                    'foreground',
                    NULL,
                    NULL,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    'exact',
                    '{}'::jsonb
                  ),
                  (
                    'cursor-estimated-1',
                    'telemetry-repo',
                    'cursor:cursor-session-1',
                    'episode-2',
                    'cursor',
                    'cursor-session-1',
                    'sidecar-1',
                    'cursor_statusline_sidecar',
                    '2026-03-18T10:10:05+00:00',
                    'foreground',
                    'anthropic',
                    'claude-3-7-sonnet',
                    30,
                    10,
                    0,
                    0,
                    0,
                    0,
                    'estimated',
                    '{}'::jsonb
                  )
                """
            )
        )

    assert_relation_exists("usage_session_tokens")
    session_rows = fetch_relation_rows(
        "usage_session_tokens",
        where_sql="repo_id = :repo_id AND host_app = :host_app AND host_session_key = :host_session_key",
        params={"repo_id": "telemetry-repo", "host_app": "cursor", "host_session_key": "cursor-session-1"},
    )
    health_rows = fetch_relation_rows(
        "usage_token_capture_health",
        where_sql="repo_id = :repo_id AND host_app = :host_app",
        params={"repo_id": "telemetry-repo", "host_app": "cursor"},
    )

    assert len(session_rows) == 1
    assert session_rows[0]["fresh_work_tokens"] == 40
    assert session_rows[0]["uses_exact_rows"] is False
    assert session_rows[0]["uses_estimated_rows"] is True
    assert session_rows[0]["has_cursor_zero_rows"] is True
    assert len(health_rows) == 1
    assert health_rows[0]["sessions_with_estimated_only_data"] == 1
    assert health_rows[0]["cursor_zero_only_sessions"] == 1


def test_usage_problem_tokens_should_sum_usage_between_problem_creation_and_first_solution_and_latest_solution_when_only_one_solution_exists(
    integration_engine,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """usage_problem_tokens should expose identical first/latest metrics when one solution exists."""

    with integration_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO episodes (id, repo_id, host_app, thread_id, status, started_at, created_at)
                VALUES ('episode-problem-1', 'telemetry-repo', 'codex', 'codex:session-problem', 'active', '2026-03-18T10:00:00+00:00', '2026-03-18T10:00:00+00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO episode_events (id, episode_id, seq, host_event_key, source, content, created_at)
                VALUES ('evt-problem-1', 'episode-problem-1', 1, 'host-problem-1', 'user', '{}'::text, '2026-03-18T10:00:05+00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO evidence_refs (id, repo_id, ref, episode_event_id, created_at)
                VALUES ('evidence-problem-1', 'telemetry-repo', 'evt-problem-1', 'evt-problem-1', '2026-03-18T10:00:06+00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO memories (id, repo_id, scope, kind, text, created_at, archived)
                VALUES
                  ('problem-1', 'telemetry-repo', 'repo', 'problem', 'lock timeout', '2026-03-18T10:00:10+00:00', FALSE),
                  ('solution-1', 'telemetry-repo', 'repo', 'solution', 'raise lock timeout', '2026-03-18T10:02:00+00:00', FALSE)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO memory_evidence (memory_id, evidence_id)
                VALUES ('problem-1', 'evidence-problem-1')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO problem_attempts (problem_id, attempt_id, role, created_at)
                VALUES ('problem-1', 'solution-1', 'solution', '2026-03-18T10:02:00+00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO model_usage (
                    id,
                    repo_id,
                    thread_id,
                    episode_id,
                    host_app,
                    host_session_key,
                    host_usage_key,
                    source_kind,
                    occurred_at,
                    agent_role,
                    provider,
                    model_id,
                    input_tokens,
                    output_tokens,
                    reasoning_output_tokens,
                    cached_input_tokens_total,
                    cache_read_input_tokens,
                    cache_creation_input_tokens,
                    capture_quality,
                    raw_usage_json
                ) VALUES
                  (
                    'problem-usage-before',
                    'telemetry-repo',
                    'codex:session-problem',
                    'episode-problem-1',
                    'codex',
                    'session-problem',
                    'usage-before',
                    'codex_transcript',
                    '2026-03-18T10:00:20+00:00',
                    'foreground',
                    'openai',
                    NULL,
                    100,
                    20,
                    5,
                    10,
                    0,
                    0,
                    'exact',
                    '{}'::jsonb
                  ),
                  (
                    'problem-usage-after',
                    'telemetry-repo',
                    'codex:session-problem',
                    'episode-problem-1',
                    'codex',
                    'session-problem',
                    'usage-after',
                    'codex_transcript',
                    '2026-03-18T10:03:00+00:00',
                    'foreground',
                    'openai',
                    NULL,
                    500,
                    100,
                    0,
                    0,
                    0,
                    0,
                    'exact',
                    '{}'::jsonb
                  )
                """
            )
        )

    assert_relation_exists("usage_problem_tokens")
    rows = fetch_relation_rows(
        "usage_problem_tokens",
        where_sql="repo_id = :repo_id AND problem_id = :problem_id",
        params={"repo_id": "telemetry-repo", "problem_id": "problem-1"},
    )

    assert len(rows) == 1
    assert rows[0]["solution_count"] == 1
    assert rows[0]["has_multiple_solutions"] is False
    assert rows[0]["solution_id"] == "solution-1"
    assert rows[0]["latest_solution_id"] == "solution-1"
    assert rows[0]["fresh_work_tokens"] == 120
    assert rows[0]["all_tokens_including_cache"] == 130
    assert rows[0]["latest_fresh_work_tokens"] == 120
    assert rows[0]["latest_all_tokens_including_cache"] == 130


def test_usage_problem_tokens_should_expose_first_and_latest_solution_metrics_when_multiple_solutions_exist(
    integration_engine,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """usage_problem_tokens and usage_problem_read_roi should work across first and latest multi-solution windows."""

    with integration_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO episodes (id, repo_id, host_app, thread_id, status, started_at, created_at)
                VALUES ('episode-problem-2', 'telemetry-repo', 'codex', 'codex:session-multi', 'active', '2026-03-18T11:00:00+00:00', '2026-03-18T11:00:00+00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO episode_events (id, episode_id, seq, host_event_key, source, content, created_at)
                VALUES ('evt-problem-2', 'episode-problem-2', 1, 'host-problem-2', 'user', '{}'::text, '2026-03-18T11:00:05+00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO evidence_refs (id, repo_id, ref, episode_event_id, created_at)
                VALUES ('evidence-problem-2', 'telemetry-repo', 'evt-problem-2', 'evt-problem-2', '2026-03-18T11:00:06+00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO memories (id, repo_id, scope, kind, text, created_at, archived)
                VALUES
                  ('problem-2', 'telemetry-repo', 'repo', 'problem', 'flaky latest metric', '2026-03-18T11:00:10+00:00', FALSE),
                  ('solution-2a', 'telemetry-repo', 'repo', 'solution', 'first workaround', '2026-03-18T11:02:00+00:00', FALSE),
                  ('solution-2b', 'telemetry-repo', 'repo', 'solution', 'final fix', '2026-03-18T11:04:00+00:00', FALSE)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO memory_evidence (memory_id, evidence_id)
                VALUES ('problem-2', 'evidence-problem-2')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO problem_attempts (problem_id, attempt_id, role, created_at)
                VALUES
                  ('problem-2', 'solution-2a', 'solution', '2026-03-18T11:02:00+00:00'),
                  ('problem-2', 'solution-2b', 'solution', '2026-03-18T11:04:00+00:00')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO model_usage (
                    id,
                    repo_id,
                    thread_id,
                    episode_id,
                    host_app,
                    host_session_key,
                    host_usage_key,
                    source_kind,
                    occurred_at,
                    agent_role,
                    provider,
                    model_id,
                    input_tokens,
                    output_tokens,
                    reasoning_output_tokens,
                    cached_input_tokens_total,
                    cache_read_input_tokens,
                    cache_creation_input_tokens,
                    capture_quality,
                    raw_usage_json
                ) VALUES
                  (
                    'problem-2-usage-a',
                    'telemetry-repo',
                    'codex:session-multi',
                    'episode-problem-2',
                    'codex',
                    'session-multi',
                    'usage-a',
                    'codex_transcript',
                    '2026-03-18T11:00:20+00:00',
                    'foreground',
                    'openai',
                    NULL,
                    100,
                    20,
                    5,
                    10,
                    0,
                    0,
                    'exact',
                    '{}'::jsonb
                  ),
                  (
                    'problem-2-usage-b',
                    'telemetry-repo',
                    'codex:session-multi',
                    'episode-problem-2',
                    'codex',
                    'session-multi',
                    'usage-b',
                    'codex_transcript',
                    '2026-03-18T11:03:00+00:00',
                    'foreground',
                    'openai',
                    NULL,
                    50,
                    10,
                    0,
                    5,
                    0,
                    0,
                    'exact',
                    '{}'::jsonb
                  ),
                  (
                    'problem-2-usage-c',
                    'telemetry-repo',
                    'codex:session-multi',
                    'episode-problem-2',
                    'codex',
                    'session-multi',
                    'usage-c',
                    'codex_transcript',
                    '2026-03-18T11:05:00+00:00',
                    'foreground',
                    'openai',
                    NULL,
                    500,
                    100,
                    0,
                    0,
                    0,
                    0,
                    'exact',
                    '{}'::jsonb
                  )
                """
            )
        )
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
                ) VALUES
                  (
                    'inv-problem-2-read-1',
                    'read',
                    'telemetry-repo',
                    '/tmp/telemetry-repo',
                    FALSE,
                    'codex',
                    'session-multi',
                    'codex:session-multi',
                    'episode-problem-2',
                    1,
                    FALSE,
                    'ok',
                    NULL,
                    NULL,
                    NULL,
                    8,
                    FALSE,
                    FALSE,
                    '2026-03-18T11:00:30+00:00'
                  ),
                  (
                    'inv-problem-2-read-2',
                    'read',
                    'telemetry-repo',
                    '/tmp/telemetry-repo',
                    FALSE,
                    'codex',
                    'session-multi',
                    'codex:session-multi',
                    'episode-problem-2',
                    1,
                    FALSE,
                    'ok',
                    NULL,
                    NULL,
                    NULL,
                    8,
                    FALSE,
                    FALSE,
                    '2026-03-18T11:03:30+00:00'
                  )
                """
            )
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
                    zero_results,
                    pack_char_count,
                    pack_token_estimate,
                    pack_token_estimate_method,
                    direct_token_estimate,
                    explicit_related_token_estimate,
                    implicit_related_token_estimate
                ) VALUES
                  (
                    'inv-problem-2-read-1',
                    'first-solution read',
                    'targeted',
                    8,
                    8,
                    TRUE,
                    '["problem","solution"]'::jsonb,
                    1,
                    1,
                    1,
                    3,
                    FALSE,
                    480,
                    120,
                    'json_compact_chars_div4_v1',
                    40,
                    30,
                    20
                  ),
                  (
                    'inv-problem-2-read-2',
                    'latest-solution read',
                    'targeted',
                    8,
                    8,
                    TRUE,
                    '["problem"]'::jsonb,
                    0,
                    0,
                    0,
                    0,
                    TRUE,
                    80,
                    20,
                    'json_compact_chars_div4_v1',
                    0,
                    0,
                    0
                  )
                """
            )
        )

    assert_relation_exists("usage_problem_tokens")
    rows = fetch_relation_rows(
        "usage_problem_tokens",
        where_sql="repo_id = :repo_id AND problem_id = :problem_id",
        params={"repo_id": "telemetry-repo", "problem_id": "problem-2"},
    )

    assert len(rows) == 1
    assert rows[0]["solution_count"] == 2
    assert rows[0]["has_multiple_solutions"] is True
    assert rows[0]["solution_id"] == "solution-2a"
    assert rows[0]["latest_solution_id"] == "solution-2b"
    assert rows[0]["fresh_work_tokens"] == 120
    assert rows[0]["all_tokens_including_cache"] == 130
    assert rows[0]["latest_fresh_work_tokens"] == 180
    assert rows[0]["latest_all_tokens_including_cache"] == 195

    assert_relation_exists("usage_problem_read_roi")
    roi_rows = fetch_relation_rows(
        "usage_problem_read_roi",
        where_sql="repo_id = :repo_id AND problem_id = :problem_id",
        params={"repo_id": "telemetry-repo", "problem_id": "problem-2"},
    )

    assert len(roi_rows) == 1
    assert roi_rows[0]["read_count_before_first_solution"] == 1
    assert roi_rows[0]["nonzero_read_count_before_first_solution"] == 1
    assert roi_rows[0]["zero_result_read_count_before_first_solution"] == 0
    assert roi_rows[0]["read_token_estimate_count_before_first_solution"] == 1
    assert roi_rows[0]["shellbrain_pack_tokens_before_first_solution"] == 120
    assert roi_rows[0]["shellbrain_direct_tokens_before_first_solution"] == 40
    assert roi_rows[0]["shellbrain_explicit_tokens_before_first_solution"] == 30
    assert roi_rows[0]["shellbrain_implicit_tokens_before_first_solution"] == 20
    assert roi_rows[0]["read_cohort_before_first_solution"] == "nonzero"
    assert roi_rows[0]["read_count_before_latest_solution"] == 2
    assert roi_rows[0]["nonzero_read_count_before_latest_solution"] == 1
    assert roi_rows[0]["zero_result_read_count_before_latest_solution"] == 1
    assert roi_rows[0]["read_token_estimate_count_before_latest_solution"] == 2
    assert roi_rows[0]["shellbrain_pack_tokens_before_latest_solution"] == 140
    assert roi_rows[0]["shellbrain_direct_tokens_before_latest_solution"] == 40
    assert roi_rows[0]["shellbrain_explicit_tokens_before_latest_solution"] == 30
    assert roi_rows[0]["shellbrain_implicit_tokens_before_latest_solution"] == 20
    assert roi_rows[0]["read_cohort_before_latest_solution"] == "nonzero"


def test_usage_read_before_solve_roi_should_bucket_none_zero_only_and_nonzero_read_cohorts(
    integration_engine,
    assert_relation_exists,
    fetch_relation_rows,
) -> None:
    """usage_read_before_solve_roi should aggregate per-repo cohorts across first and latest solve windows."""

    with integration_engine.begin() as conn:
        _insert_problem_with_solution_and_optional_read(
            conn,
            suffix="none",
            fresh_work_tokens=120,
            all_tokens_including_cache=140,
            read_kind="none",
            read_pack_tokens=None,
            direct_tokens=None,
            explicit_tokens=None,
            implicit_tokens=None,
        )
        _insert_problem_with_solution_and_optional_read(
            conn,
            suffix="zero",
            fresh_work_tokens=200,
            all_tokens_including_cache=220,
            read_kind="zero_only",
            read_pack_tokens=20,
            direct_tokens=0,
            explicit_tokens=0,
            implicit_tokens=0,
        )
        _insert_problem_with_solution_and_optional_read(
            conn,
            suffix="nonzero",
            fresh_work_tokens=300,
            all_tokens_including_cache=360,
            read_kind="nonzero",
            read_pack_tokens=120,
            direct_tokens=40,
            explicit_tokens=30,
            implicit_tokens=20,
        )

    assert_relation_exists("usage_read_before_solve_roi")
    rows = fetch_relation_rows(
        "usage_read_before_solve_roi",
        where_sql="repo_id = :repo_id",
        params={"repo_id": "telemetry-repo"},
        order_by="solve_window ASC, read_cohort ASC",
    )

    assert len(rows) == 6
    first_rows = [row for row in rows if row["solve_window"] == "first_solution"]
    latest_rows = [row for row in rows if row["solve_window"] == "latest_solution"]

    assert {row["read_cohort"] for row in first_rows} == {"none", "zero_only", "nonzero"}
    assert {row["read_cohort"] for row in latest_rows} == {"none", "zero_only", "nonzero"}

    first_by_cohort = {row["read_cohort"]: row for row in first_rows}
    assert first_by_cohort["none"]["problem_count"] == 1
    assert first_by_cohort["none"]["avg_fresh_work_tokens"] == 120
    assert first_by_cohort["none"]["avg_shellbrain_pack_tokens"] == 0
    assert first_by_cohort["none"]["avg_read_count"] == 0
    assert first_by_cohort["zero_only"]["problem_count"] == 1
    assert first_by_cohort["zero_only"]["avg_fresh_work_tokens"] == 200
    assert first_by_cohort["zero_only"]["avg_shellbrain_pack_tokens"] == 20
    assert first_by_cohort["zero_only"]["avg_shellbrain_direct_tokens"] == 0
    assert first_by_cohort["zero_only"]["avg_read_count"] == 1
    assert first_by_cohort["nonzero"]["problem_count"] == 1
    assert first_by_cohort["nonzero"]["avg_fresh_work_tokens"] == 300
    assert first_by_cohort["nonzero"]["avg_shellbrain_pack_tokens"] == 120
    assert first_by_cohort["nonzero"]["avg_shellbrain_direct_tokens"] == 40
    assert first_by_cohort["nonzero"]["avg_shellbrain_explicit_tokens"] == 30
    assert first_by_cohort["nonzero"]["avg_shellbrain_implicit_tokens"] == 20
    assert first_by_cohort["nonzero"]["avg_read_count"] == 1

    latest_by_cohort = {row["read_cohort"]: row for row in latest_rows}
    assert latest_by_cohort["none"]["problem_count"] == 1
    assert latest_by_cohort["zero_only"]["problem_count"] == 1
    assert latest_by_cohort["nonzero"]["problem_count"] == 1


def _insert_problem_with_solution_and_optional_read(
    conn,
    *,
    suffix: str,
    fresh_work_tokens: int,
    all_tokens_including_cache: int,
    read_kind: str,
    read_pack_tokens: int | None,
    direct_tokens: int | None,
    explicit_tokens: int | None,
    implicit_tokens: int | None,
) -> None:
    """Insert one single-solution problem plus optional read telemetry for ROI view tests."""

    thread_id = f"codex:session-{suffix}"
    episode_id = f"episode-problem-{suffix}"
    event_id = f"evt-problem-{suffix}"
    evidence_id = f"evidence-problem-{suffix}"
    problem_id = f"problem-{suffix}"
    solution_id = f"solution-{suffix}"
    host_session_key = f"session-{suffix}"
    base_time = {
        "none": "2026-03-18T12:00:00+00:00",
        "zero": "2026-03-18T13:00:00+00:00",
        "nonzero": "2026-03-18T14:00:00+00:00",
    }[suffix]
    if suffix == "none":
        problem_created_at = "2026-03-18T12:00:10+00:00"
        solution_created_at = "2026-03-18T12:02:00+00:00"
        usage_at = "2026-03-18T12:00:20+00:00"
        read_at = None
    elif suffix == "zero":
        problem_created_at = "2026-03-18T13:00:10+00:00"
        solution_created_at = "2026-03-18T13:02:00+00:00"
        usage_at = "2026-03-18T13:00:20+00:00"
        read_at = "2026-03-18T13:00:40+00:00"
    else:
        problem_created_at = "2026-03-18T14:00:10+00:00"
        solution_created_at = "2026-03-18T14:02:00+00:00"
        usage_at = "2026-03-18T14:00:20+00:00"
        read_at = "2026-03-18T14:00:40+00:00"

    conn.execute(
        text(
            """
            INSERT INTO episodes (id, repo_id, host_app, thread_id, status, started_at, created_at)
            VALUES (:episode_id, 'telemetry-repo', 'codex', :thread_id, 'active', :started_at, :started_at)
            """
        ),
        {"episode_id": episode_id, "thread_id": thread_id, "started_at": base_time},
    )
    conn.execute(
        text(
            """
            INSERT INTO episode_events (id, episode_id, seq, host_event_key, source, content, created_at)
            VALUES (:event_id, :episode_id, 1, :host_event_key, 'user', '{}'::text, :created_at)
            """
        ),
        {"event_id": event_id, "episode_id": episode_id, "host_event_key": f"host-{suffix}", "created_at": base_time},
    )
    conn.execute(
        text(
            """
            INSERT INTO evidence_refs (id, repo_id, ref, episode_event_id, created_at)
            VALUES (:evidence_id, 'telemetry-repo', :event_id, :event_id, :created_at)
            """
        ),
        {"evidence_id": evidence_id, "event_id": event_id, "created_at": base_time},
    )
    conn.execute(
        text(
            """
            INSERT INTO memories (id, repo_id, scope, kind, text, created_at, archived)
            VALUES
              (:problem_id, 'telemetry-repo', 'repo', 'problem', :problem_text, :problem_created_at, FALSE),
              (:solution_id, 'telemetry-repo', 'repo', 'solution', :solution_text, :solution_created_at, FALSE)
            """
        ),
        {
            "problem_id": problem_id,
            "problem_text": f"problem {suffix}",
            "problem_created_at": problem_created_at,
            "solution_id": solution_id,
            "solution_text": f"solution {suffix}",
            "solution_created_at": solution_created_at,
        },
    )
    conn.execute(
        text("INSERT INTO memory_evidence (memory_id, evidence_id) VALUES (:problem_id, :evidence_id)"),
        {"problem_id": problem_id, "evidence_id": evidence_id},
    )
    conn.execute(
        text(
            """
            INSERT INTO problem_attempts (problem_id, attempt_id, role, created_at)
            VALUES (:problem_id, :solution_id, 'solution', :solution_created_at)
            """
        ),
        {"problem_id": problem_id, "solution_id": solution_id, "solution_created_at": solution_created_at},
    )
    conn.execute(
        text(
            """
            INSERT INTO model_usage (
                id,
                repo_id,
                thread_id,
                episode_id,
                host_app,
                host_session_key,
                host_usage_key,
                source_kind,
                occurred_at,
                agent_role,
                provider,
                model_id,
                input_tokens,
                output_tokens,
                reasoning_output_tokens,
                cached_input_tokens_total,
                cache_read_input_tokens,
                cache_creation_input_tokens,
                capture_quality,
                raw_usage_json
            ) VALUES (
                :usage_id,
                'telemetry-repo',
                :thread_id,
                :episode_id,
                'codex',
                :host_session_key,
                :host_usage_key,
                'codex_transcript',
                :occurred_at,
                'foreground',
                'openai',
                NULL,
                :input_tokens,
                20,
                5,
                :cached_input_tokens_total,
                0,
                0,
                'exact',
                '{}'::jsonb
            )
            """
        ),
        {
            "usage_id": f"usage-{suffix}",
            "thread_id": thread_id,
            "episode_id": episode_id,
            "host_session_key": host_session_key,
            "host_usage_key": f"usage-{suffix}",
            "occurred_at": usage_at,
            "input_tokens": fresh_work_tokens - 20,
            "cached_input_tokens_total": all_tokens_including_cache - fresh_work_tokens,
        },
    )

    if read_kind == "none":
        return

    zero_results = read_kind == "zero_only"
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
                :invocation_id,
                'read',
                'telemetry-repo',
                '/tmp/telemetry-repo',
                FALSE,
                'codex',
                :host_session_key,
                :thread_id,
                :episode_id,
                1,
                FALSE,
                'ok',
                NULL,
                NULL,
                NULL,
                8,
                FALSE,
                FALSE,
                :read_at
            )
            """
        ),
        {
            "invocation_id": f"inv-read-{suffix}",
            "host_session_key": host_session_key,
            "thread_id": thread_id,
            "episode_id": episode_id,
            "read_at": read_at,
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
                zero_results,
                pack_char_count,
                pack_token_estimate,
                pack_token_estimate_method,
                direct_token_estimate,
                explicit_related_token_estimate,
                implicit_related_token_estimate
            ) VALUES (
                :invocation_id,
                :query_text,
                'targeted',
                8,
                8,
                TRUE,
                '["problem"]'::jsonb,
                :direct_count,
                :explicit_count,
                :implicit_count,
                :total_returned,
                :zero_results,
                :pack_char_count,
                :pack_token_estimate,
                'json_compact_chars_div4_v1',
                :direct_token_estimate,
                :explicit_related_token_estimate,
                :implicit_related_token_estimate
            )
            """
        ),
        {
            "invocation_id": f"inv-read-{suffix}",
            "query_text": f"read {suffix}",
            "direct_count": 0 if zero_results else 1,
            "explicit_count": 0 if zero_results else 1,
            "implicit_count": 0 if zero_results else 1,
            "total_returned": 0 if zero_results else 3,
            "zero_results": zero_results,
            "pack_char_count": (read_pack_tokens or 0) * 4,
            "pack_token_estimate": read_pack_tokens,
            "direct_token_estimate": direct_tokens,
            "explicit_related_token_estimate": explicit_tokens,
            "implicit_related_token_estimate": implicit_tokens,
        },
    )


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
