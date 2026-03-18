"""This module defines view SQL strings used to build derived read-model views."""


CURRENT_FACT_SNAPSHOT_SQL = """
CREATE OR REPLACE VIEW current_fact_snapshot AS
SELECT m.*
FROM memories m
WHERE m.kind = 'fact'
  AND m.archived = FALSE
  AND NOT EXISTS (
    SELECT 1 FROM fact_updates fu WHERE fu.old_fact_id = m.id
  );
"""


GLOBAL_UTILITY_SQL = """
CREATE OR REPLACE VIEW global_utility AS
SELECT memory_id, AVG(vote) AS utility_mean, COUNT(*) AS observations
FROM utility_observations
GROUP BY memory_id;
"""


USAGE_COMMAND_DAILY_SQL = """
CREATE OR REPLACE VIEW usage_command_daily AS
SELECT
  repo_id,
  date_trunc('day', created_at AT TIME ZONE 'UTC') AS day_utc,
  command,
  outcome,
  COUNT(*)::INTEGER AS invocation_count,
  AVG(total_latency_ms)::DOUBLE PRECISION AS avg_latency_ms
FROM operation_invocations
GROUP BY repo_id, date_trunc('day', created_at AT TIME ZONE 'UTC'), command, outcome;
"""


USAGE_MEMORY_RETRIEVAL_SQL = """
CREATE OR REPLACE VIEW usage_memory_retrieval AS
SELECT
  oi.repo_id,
  rri.memory_id,
  rri.kind,
  rri.section,
  COUNT(*)::INTEGER AS retrieval_count,
  MAX(oi.created_at) AS last_seen_at
FROM read_result_items rri
JOIN operation_invocations oi ON oi.id = rri.invocation_id
GROUP BY oi.repo_id, rri.memory_id, rri.kind, rri.section;
"""


USAGE_WRITE_EFFECTS_SQL = """
CREATE OR REPLACE VIEW usage_write_effects AS
SELECT
  wei.repo_id,
  date_trunc('day', oi.created_at AT TIME ZONE 'UTC') AS day_utc,
  wei.effect_type,
  COUNT(*)::INTEGER AS effect_count
FROM write_effect_items wei
JOIN operation_invocations oi ON oi.id = wei.invocation_id
GROUP BY wei.repo_id, date_trunc('day', oi.created_at AT TIME ZONE 'UTC'), wei.effect_type;
"""


USAGE_SYNC_HEALTH_SQL = """
CREATE OR REPLACE VIEW usage_sync_health AS
WITH sync_grouped AS (
  SELECT
    repo_id,
    host_app,
    date_trunc('day', created_at AT TIME ZONE 'UTC') AS day_utc,
    COUNT(*)::INTEGER AS sync_run_count,
    COUNT(*) FILTER (WHERE outcome = 'error')::INTEGER AS failed_sync_count,
    COALESCE(SUM(imported_event_count), 0)::INTEGER AS imported_event_count
  FROM episode_sync_runs
  GROUP BY repo_id, host_app, date_trunc('day', created_at AT TIME ZONE 'UTC')
),
tool_grouped AS (
  SELECT
    esr.repo_id,
    esr.host_app,
    date_trunc('day', esr.created_at AT TIME ZONE 'UTC') AS day_utc,
    estt.tool_type,
    SUM(estt.event_count)::INTEGER AS event_count
  FROM episode_sync_tool_types estt
  JOIN episode_sync_runs esr ON esr.id = estt.sync_run_id
  GROUP BY esr.repo_id, esr.host_app, date_trunc('day', esr.created_at AT TIME ZONE 'UTC'), estt.tool_type
),
tool_objects AS (
  SELECT
    repo_id,
    host_app,
    day_utc,
    jsonb_object_agg(tool_type, event_count ORDER BY tool_type) AS tool_type_counts
  FROM tool_grouped
  GROUP BY repo_id, host_app, day_utc
)
SELECT
  sg.repo_id,
  sg.host_app,
  sg.day_utc,
  sg.sync_run_count,
  sg.failed_sync_count,
  sg.imported_event_count,
  COALESCE(toj.tool_type_counts, '{}'::jsonb) AS tool_type_counts
FROM sync_grouped sg
LEFT JOIN tool_objects toj
  ON toj.repo_id = sg.repo_id
 AND toj.host_app = sg.host_app
 AND toj.day_utc = sg.day_utc;
"""


USAGE_SESSION_PROTOCOL_SQL = """
CREATE OR REPLACE VIEW usage_session_protocol AS
SELECT
  oi.repo_id,
  oi.selected_thread_id,
  COUNT(*) FILTER (WHERE oi.command = 'read')::INTEGER AS read_count,
  COUNT(*) FILTER (WHERE oi.command = 'events')::INTEGER AS events_count,
  COUNT(*) FILTER (WHERE oi.command IN ('create', 'update'))::INTEGER AS write_count,
  COUNT(*) FILTER (
    WHERE oi.command = 'read'
      AND COALESCE(ris.zero_results, FALSE)
  )::INTEGER AS zero_result_read_count,
  COUNT(*) FILTER (WHERE oi.selection_ambiguous)::INTEGER AS ambiguous_selection_count,
  COUNT(*) FILTER (
    WHERE oi.command IN ('create', 'update')
      AND EXISTS (
        SELECT 1
        FROM operation_invocations prior_events
        WHERE prior_events.repo_id = oi.repo_id
          AND prior_events.selected_thread_id = oi.selected_thread_id
          AND prior_events.command = 'events'
          AND prior_events.created_at < oi.created_at
      )
  )::INTEGER AS writes_preceded_by_events_count,
  COUNT(*) FILTER (
    WHERE oi.command = 'events'
      AND NOT EXISTS (
        SELECT 1
        FROM operation_invocations later_writes
        WHERE later_writes.repo_id = oi.repo_id
          AND later_writes.selected_thread_id = oi.selected_thread_id
          AND later_writes.command IN ('create', 'update')
          AND later_writes.created_at > oi.created_at
      )
  )::INTEGER AS events_without_following_write_count
FROM operation_invocations oi
LEFT JOIN read_invocation_summaries ris ON ris.invocation_id = oi.id
WHERE oi.selected_thread_id IS NOT NULL
GROUP BY oi.repo_id, oi.selected_thread_id;
"""
