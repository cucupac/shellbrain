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


USAGE_SESSION_TOKENS_SQL = """
CREATE OR REPLACE VIEW usage_session_tokens AS
WITH session_quality AS (
  SELECT
    repo_id,
    host_app,
    host_session_key,
    BOOL_OR(capture_quality = 'exact') AS has_exact_rows,
    BOOL_OR(
      capture_quality = 'exact'
      AND (
        COALESCE(input_tokens, 0) > 0
        OR COALESCE(output_tokens, 0) > 0
        OR COALESCE(cached_input_tokens_total, 0) > 0
        OR COALESCE(reasoning_output_tokens, 0) > 0
      )
    ) AS has_nonzero_exact_rows,
    BOOL_OR(capture_quality = 'estimated') AS has_estimated_rows,
    BOOL_OR(
      source_kind = 'cursor_state_vscdb'
      AND COALESCE(input_tokens, 0) = 0
      AND COALESCE(output_tokens, 0) = 0
      AND COALESCE(cached_input_tokens_total, 0) = 0
      AND COALESCE(reasoning_output_tokens, 0) = 0
    ) AS has_cursor_zero_rows
  FROM model_usage
  GROUP BY repo_id, host_app, host_session_key
),
preferred_rows AS (
  SELECT mu.*
  FROM model_usage mu
  JOIN session_quality sq
    ON sq.repo_id = mu.repo_id
   AND sq.host_app = mu.host_app
   AND sq.host_session_key = mu.host_session_key
  WHERE (
    sq.has_nonzero_exact_rows
    AND mu.capture_quality = 'exact'
  ) OR (
    NOT sq.has_nonzero_exact_rows
    AND mu.capture_quality = 'estimated'
  ) OR (
    NOT sq.has_nonzero_exact_rows
    AND NOT sq.has_estimated_rows
    AND sq.has_exact_rows
    AND mu.capture_quality = 'exact'
  )
)
SELECT
  pr.repo_id,
  pr.host_app,
  pr.host_session_key,
  MIN(pr.thread_id) FILTER (WHERE pr.thread_id IS NOT NULL) AS thread_id,
  MIN(pr.episode_id) FILTER (WHERE pr.episode_id IS NOT NULL) AS episode_id,
  MIN(pr.occurred_at) AS first_usage_at,
  MAX(pr.occurred_at) AS last_usage_at,
  COUNT(*)::INTEGER AS usage_row_count,
  COALESCE(SUM(pr.input_tokens), 0)::BIGINT AS input_tokens,
  COALESCE(SUM(pr.output_tokens), 0)::BIGINT AS output_tokens,
  COALESCE(SUM(pr.reasoning_output_tokens), 0)::BIGINT AS reasoning_output_tokens,
  COALESCE(SUM(pr.cached_input_tokens_total), 0)::BIGINT AS cached_input_tokens_total,
  COALESCE(SUM(pr.cache_read_input_tokens), 0)::BIGINT AS cache_read_input_tokens,
  COALESCE(SUM(pr.cache_creation_input_tokens), 0)::BIGINT AS cache_creation_input_tokens,
  (
    COALESCE(SUM(pr.input_tokens), 0)
    + COALESCE(SUM(pr.output_tokens), 0)
  )::BIGINT AS fresh_work_tokens,
  (
    COALESCE(SUM(pr.input_tokens), 0)
    + COALESCE(SUM(pr.cached_input_tokens_total), 0)
    + COALESCE(SUM(pr.output_tokens), 0)
  )::BIGINT AS all_tokens_including_cache,
  (
    sq.has_nonzero_exact_rows
    OR (
      NOT sq.has_nonzero_exact_rows
      AND NOT sq.has_estimated_rows
      AND sq.has_exact_rows
    )
  ) AS uses_exact_rows,
  (
    NOT sq.has_nonzero_exact_rows
    AND sq.has_estimated_rows
  ) AS uses_estimated_rows,
  sq.has_nonzero_exact_rows,
  sq.has_cursor_zero_rows
FROM preferred_rows pr
JOIN session_quality sq
  ON sq.repo_id = pr.repo_id
 AND sq.host_app = pr.host_app
 AND sq.host_session_key = pr.host_session_key
GROUP BY
  pr.repo_id,
  pr.host_app,
  pr.host_session_key,
  sq.has_exact_rows,
  sq.has_estimated_rows,
  sq.has_nonzero_exact_rows,
  sq.has_cursor_zero_rows;
"""


USAGE_PROBLEM_TOKENS_SQL = """
CREATE OR REPLACE VIEW usage_problem_tokens AS
WITH session_quality AS (
  SELECT
    repo_id,
    host_app,
    host_session_key,
    BOOL_OR(capture_quality = 'exact') AS has_exact_rows,
    BOOL_OR(
      capture_quality = 'exact'
      AND (
        COALESCE(input_tokens, 0) > 0
        OR COALESCE(output_tokens, 0) > 0
        OR COALESCE(cached_input_tokens_total, 0) > 0
        OR COALESCE(reasoning_output_tokens, 0) > 0
      )
    ) AS has_nonzero_exact_rows,
    BOOL_OR(capture_quality = 'estimated') AS has_estimated_rows
  FROM model_usage
  GROUP BY repo_id, host_app, host_session_key
),
preferred_rows AS (
  SELECT mu.*
  FROM model_usage mu
  JOIN session_quality sq
    ON sq.repo_id = mu.repo_id
   AND sq.host_app = mu.host_app
   AND sq.host_session_key = mu.host_session_key
  WHERE (
    sq.has_nonzero_exact_rows
    AND mu.capture_quality = 'exact'
  ) OR (
    NOT sq.has_nonzero_exact_rows
    AND mu.capture_quality = 'estimated'
  ) OR (
    NOT sq.has_nonzero_exact_rows
    AND NOT sq.has_estimated_rows
    AND sq.has_exact_rows
    AND mu.capture_quality = 'exact'
  )
),
problem_threads AS (
  SELECT
    p.id AS problem_id,
    p.repo_id,
    p.created_at AS problem_created_at,
    (
      ARRAY_AGG(ep.thread_id ORDER BY ee.created_at ASC, ee.seq ASC)
      FILTER (WHERE ep.thread_id IS NOT NULL)
    )[1] AS thread_id
  FROM memories p
  JOIN memory_evidence me ON me.memory_id = p.id
  JOIN evidence_refs er ON er.id = me.evidence_id
  JOIN episode_events ee ON ee.id = COALESCE(er.episode_event_id, er.ref)
  JOIN episodes ep ON ep.id = ee.episode_id
  WHERE p.kind = 'problem'
  GROUP BY p.id, p.repo_id, p.created_at
),
solution_candidates AS (
  SELECT
    pa.problem_id,
    s.id AS solution_id,
    s.created_at AS solution_created_at,
    ROW_NUMBER() OVER (
      PARTITION BY pa.problem_id
      ORDER BY s.created_at ASC, s.id ASC
    ) AS first_row_num,
    ROW_NUMBER() OVER (
      PARTITION BY pa.problem_id
      ORDER BY s.created_at DESC, s.id DESC
    ) AS latest_row_num,
    COUNT(*) OVER (
      PARTITION BY pa.problem_id
    )::INTEGER AS solution_count
  FROM problem_attempts pa
  JOIN memories s ON s.id = pa.attempt_id
  WHERE pa.role = 'solution'
    AND s.kind = 'solution'
),
problem_windows AS (
  SELECT
    pt.repo_id,
    pt.problem_id,
    pt.thread_id,
    pt.problem_created_at,
    fs.solution_count,
    fs.solution_id,
    fs.solution_created_at,
    ls.solution_id AS latest_solution_id,
    ls.solution_created_at AS latest_solution_created_at
  FROM problem_threads pt
  JOIN solution_candidates fs
    ON fs.problem_id = pt.problem_id
   AND fs.first_row_num = 1
  JOIN solution_candidates ls
    ON ls.problem_id = pt.problem_id
   AND ls.latest_row_num = 1
  WHERE pt.thread_id IS NOT NULL
),
first_solution_usage AS (
  SELECT
    pw.repo_id,
    pw.problem_id,
    COUNT(pr.id)::INTEGER AS usage_row_count,
    COALESCE(SUM(pr.input_tokens), 0)::BIGINT AS input_tokens,
    COALESCE(SUM(pr.output_tokens), 0)::BIGINT AS output_tokens,
    COALESCE(SUM(pr.reasoning_output_tokens), 0)::BIGINT AS reasoning_output_tokens,
    COALESCE(SUM(pr.cached_input_tokens_total), 0)::BIGINT AS cached_input_tokens_total,
    COALESCE(SUM(pr.cache_read_input_tokens), 0)::BIGINT AS cache_read_input_tokens,
    COALESCE(SUM(pr.cache_creation_input_tokens), 0)::BIGINT AS cache_creation_input_tokens,
    (
      COALESCE(SUM(pr.input_tokens), 0)
      + COALESCE(SUM(pr.output_tokens), 0)
    )::BIGINT AS fresh_work_tokens,
    (
      COALESCE(SUM(pr.input_tokens), 0)
      + COALESCE(SUM(pr.cached_input_tokens_total), 0)
      + COALESCE(SUM(pr.output_tokens), 0)
    )::BIGINT AS all_tokens_including_cache
  FROM problem_windows pw
  LEFT JOIN preferred_rows pr
    ON pr.repo_id = pw.repo_id
   AND pr.thread_id = pw.thread_id
   AND pr.occurred_at >= pw.problem_created_at
   AND pr.occurred_at <= pw.solution_created_at
  GROUP BY
    pw.repo_id,
    pw.problem_id
),
latest_solution_usage AS (
  SELECT
    pw.repo_id,
    pw.problem_id,
    COUNT(pr.id)::INTEGER AS latest_usage_row_count,
    COALESCE(SUM(pr.input_tokens), 0)::BIGINT AS latest_input_tokens,
    COALESCE(SUM(pr.output_tokens), 0)::BIGINT AS latest_output_tokens,
    COALESCE(SUM(pr.reasoning_output_tokens), 0)::BIGINT AS latest_reasoning_output_tokens,
    COALESCE(SUM(pr.cached_input_tokens_total), 0)::BIGINT AS latest_cached_input_tokens_total,
    COALESCE(SUM(pr.cache_read_input_tokens), 0)::BIGINT AS latest_cache_read_input_tokens,
    COALESCE(SUM(pr.cache_creation_input_tokens), 0)::BIGINT AS latest_cache_creation_input_tokens,
    (
      COALESCE(SUM(pr.input_tokens), 0)
      + COALESCE(SUM(pr.output_tokens), 0)
    )::BIGINT AS latest_fresh_work_tokens,
    (
      COALESCE(SUM(pr.input_tokens), 0)
      + COALESCE(SUM(pr.cached_input_tokens_total), 0)
      + COALESCE(SUM(pr.output_tokens), 0)
    )::BIGINT AS latest_all_tokens_including_cache
  FROM problem_windows pw
  LEFT JOIN preferred_rows pr
    ON pr.repo_id = pw.repo_id
   AND pr.thread_id = pw.thread_id
   AND pr.occurred_at >= pw.problem_created_at
   AND pr.occurred_at <= pw.latest_solution_created_at
  GROUP BY
    pw.repo_id,
    pw.problem_id
)
SELECT
  pw.repo_id,
  pw.problem_id,
  pw.solution_id,
  pw.thread_id,
  pw.problem_created_at,
  pw.solution_created_at,
  fsu.usage_row_count,
  fsu.input_tokens,
  fsu.output_tokens,
  fsu.reasoning_output_tokens,
  fsu.cached_input_tokens_total,
  fsu.cache_read_input_tokens,
  fsu.cache_creation_input_tokens,
  fsu.fresh_work_tokens,
  fsu.all_tokens_including_cache,
  pw.solution_count,
  (pw.solution_count > 1) AS has_multiple_solutions,
  pw.latest_solution_id,
  pw.latest_solution_created_at,
  lsu.latest_usage_row_count,
  lsu.latest_input_tokens,
  lsu.latest_output_tokens,
  lsu.latest_reasoning_output_tokens,
  lsu.latest_cached_input_tokens_total,
  lsu.latest_cache_read_input_tokens,
  lsu.latest_cache_creation_input_tokens,
  lsu.latest_fresh_work_tokens,
  lsu.latest_all_tokens_including_cache
FROM problem_windows pw
JOIN first_solution_usage fsu
  ON fsu.repo_id = pw.repo_id
 AND fsu.problem_id = pw.problem_id
JOIN latest_solution_usage lsu
  ON lsu.repo_id = pw.repo_id
 AND lsu.problem_id = pw.problem_id;
"""


USAGE_PROBLEM_READ_ROI_SQL = """
CREATE OR REPLACE VIEW usage_problem_read_roi AS
WITH successful_reads AS (
  SELECT
    oi.repo_id,
    oi.selected_thread_id AS thread_id,
    oi.created_at AS read_at,
    ris.zero_results,
    ris.pack_token_estimate,
    ris.direct_token_estimate,
    ris.explicit_related_token_estimate,
    ris.implicit_related_token_estimate
  FROM operation_invocations oi
  JOIN read_invocation_summaries ris ON ris.invocation_id = oi.id
  WHERE oi.command = 'read'
    AND oi.outcome = 'ok'
    AND oi.selected_thread_id IS NOT NULL
),
first_solution_reads AS (
  SELECT
    upt.repo_id,
    upt.problem_id,
    COUNT(sr.read_at)::INTEGER AS read_count_before_first_solution,
    COUNT(sr.read_at) FILTER (WHERE NOT COALESCE(sr.zero_results, FALSE))::INTEGER AS nonzero_read_count_before_first_solution,
    COUNT(sr.read_at) FILTER (WHERE COALESCE(sr.zero_results, FALSE))::INTEGER AS zero_result_read_count_before_first_solution,
    COUNT(sr.read_at) FILTER (WHERE sr.pack_token_estimate IS NOT NULL)::INTEGER AS read_token_estimate_count_before_first_solution,
    COALESCE(SUM(sr.pack_token_estimate), 0)::BIGINT AS shellbrain_pack_tokens_before_first_solution,
    COALESCE(SUM(sr.direct_token_estimate), 0)::BIGINT AS shellbrain_direct_tokens_before_first_solution,
    COALESCE(SUM(sr.explicit_related_token_estimate), 0)::BIGINT AS shellbrain_explicit_tokens_before_first_solution,
    COALESCE(SUM(sr.implicit_related_token_estimate), 0)::BIGINT AS shellbrain_implicit_tokens_before_first_solution,
    MIN(sr.read_at) AS first_read_before_first_solution_at,
    MAX(sr.read_at) AS last_read_before_first_solution_at
  FROM usage_problem_tokens upt
  LEFT JOIN successful_reads sr
    ON sr.repo_id = upt.repo_id
   AND sr.thread_id = upt.thread_id
   AND sr.read_at >= upt.problem_created_at
   AND sr.read_at <= upt.solution_created_at
  GROUP BY
    upt.repo_id,
    upt.problem_id
),
latest_solution_reads AS (
  SELECT
    upt.repo_id,
    upt.problem_id,
    COUNT(sr.read_at)::INTEGER AS read_count_before_latest_solution,
    COUNT(sr.read_at) FILTER (WHERE NOT COALESCE(sr.zero_results, FALSE))::INTEGER AS nonzero_read_count_before_latest_solution,
    COUNT(sr.read_at) FILTER (WHERE COALESCE(sr.zero_results, FALSE))::INTEGER AS zero_result_read_count_before_latest_solution,
    COUNT(sr.read_at) FILTER (WHERE sr.pack_token_estimate IS NOT NULL)::INTEGER AS read_token_estimate_count_before_latest_solution,
    COALESCE(SUM(sr.pack_token_estimate), 0)::BIGINT AS shellbrain_pack_tokens_before_latest_solution,
    COALESCE(SUM(sr.direct_token_estimate), 0)::BIGINT AS shellbrain_direct_tokens_before_latest_solution,
    COALESCE(SUM(sr.explicit_related_token_estimate), 0)::BIGINT AS shellbrain_explicit_tokens_before_latest_solution,
    COALESCE(SUM(sr.implicit_related_token_estimate), 0)::BIGINT AS shellbrain_implicit_tokens_before_latest_solution,
    MIN(sr.read_at) AS first_read_before_latest_solution_at,
    MAX(sr.read_at) AS last_read_before_latest_solution_at
  FROM usage_problem_tokens upt
  LEFT JOIN successful_reads sr
    ON sr.repo_id = upt.repo_id
   AND sr.thread_id = upt.thread_id
   AND sr.read_at >= upt.problem_created_at
   AND sr.read_at <= upt.latest_solution_created_at
  GROUP BY
    upt.repo_id,
    upt.problem_id
)
SELECT
  upt.*,
  fsr.read_count_before_first_solution,
  fsr.nonzero_read_count_before_first_solution,
  fsr.zero_result_read_count_before_first_solution,
  fsr.read_token_estimate_count_before_first_solution,
  fsr.shellbrain_pack_tokens_before_first_solution,
  fsr.shellbrain_direct_tokens_before_first_solution,
  fsr.shellbrain_explicit_tokens_before_first_solution,
  fsr.shellbrain_implicit_tokens_before_first_solution,
  fsr.first_read_before_first_solution_at,
  fsr.last_read_before_first_solution_at,
  CASE
    WHEN fsr.read_count_before_first_solution = 0 THEN 'none'
    WHEN fsr.nonzero_read_count_before_first_solution = 0 THEN 'zero_only'
    ELSE 'nonzero'
  END AS read_cohort_before_first_solution,
  lsr.read_count_before_latest_solution,
  lsr.nonzero_read_count_before_latest_solution,
  lsr.zero_result_read_count_before_latest_solution,
  lsr.read_token_estimate_count_before_latest_solution,
  lsr.shellbrain_pack_tokens_before_latest_solution,
  lsr.shellbrain_direct_tokens_before_latest_solution,
  lsr.shellbrain_explicit_tokens_before_latest_solution,
  lsr.shellbrain_implicit_tokens_before_latest_solution,
  lsr.first_read_before_latest_solution_at,
  lsr.last_read_before_latest_solution_at,
  CASE
    WHEN lsr.read_count_before_latest_solution = 0 THEN 'none'
    WHEN lsr.nonzero_read_count_before_latest_solution = 0 THEN 'zero_only'
    ELSE 'nonzero'
  END AS read_cohort_before_latest_solution
FROM usage_problem_tokens upt
JOIN first_solution_reads fsr
  ON fsr.repo_id = upt.repo_id
 AND fsr.problem_id = upt.problem_id
JOIN latest_solution_reads lsr
  ON lsr.repo_id = upt.repo_id
 AND lsr.problem_id = upt.problem_id;
"""


USAGE_READ_BEFORE_SOLVE_ROI_SQL = """
CREATE OR REPLACE VIEW usage_read_before_solve_roi AS
WITH problem_windows AS (
  SELECT
    repo_id,
    'first_solution'::TEXT AS solve_window,
    read_cohort_before_first_solution AS read_cohort,
    fresh_work_tokens,
    all_tokens_including_cache,
    EXTRACT(EPOCH FROM (solution_created_at - problem_created_at))::DOUBLE PRECISION AS solve_duration_seconds,
    shellbrain_pack_tokens_before_first_solution AS shellbrain_pack_tokens,
    shellbrain_direct_tokens_before_first_solution AS shellbrain_direct_tokens,
    shellbrain_explicit_tokens_before_first_solution AS shellbrain_explicit_tokens,
    shellbrain_implicit_tokens_before_first_solution AS shellbrain_implicit_tokens,
    read_count_before_first_solution AS read_count
  FROM usage_problem_read_roi
  UNION ALL
  SELECT
    repo_id,
    'latest_solution'::TEXT AS solve_window,
    read_cohort_before_latest_solution AS read_cohort,
    latest_fresh_work_tokens AS fresh_work_tokens,
    latest_all_tokens_including_cache AS all_tokens_including_cache,
    EXTRACT(EPOCH FROM (latest_solution_created_at - problem_created_at))::DOUBLE PRECISION AS solve_duration_seconds,
    shellbrain_pack_tokens_before_latest_solution AS shellbrain_pack_tokens,
    shellbrain_direct_tokens_before_latest_solution AS shellbrain_direct_tokens,
    shellbrain_explicit_tokens_before_latest_solution AS shellbrain_explicit_tokens,
    shellbrain_implicit_tokens_before_latest_solution AS shellbrain_implicit_tokens,
    read_count_before_latest_solution AS read_count
  FROM usage_problem_read_roi
)
SELECT
  repo_id,
  solve_window,
  read_cohort,
  COUNT(*)::INTEGER AS problem_count,
  AVG(fresh_work_tokens)::DOUBLE PRECISION AS avg_fresh_work_tokens,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fresh_work_tokens)::DOUBLE PRECISION AS median_fresh_work_tokens,
  AVG(all_tokens_including_cache)::DOUBLE PRECISION AS avg_all_tokens_including_cache,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY all_tokens_including_cache)::DOUBLE PRECISION AS median_all_tokens_including_cache,
  AVG(solve_duration_seconds)::DOUBLE PRECISION AS avg_solve_duration_seconds,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY solve_duration_seconds)::DOUBLE PRECISION AS median_solve_duration_seconds,
  AVG(shellbrain_pack_tokens)::DOUBLE PRECISION AS avg_shellbrain_pack_tokens,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY shellbrain_pack_tokens)::DOUBLE PRECISION AS median_shellbrain_pack_tokens,
  AVG(shellbrain_direct_tokens)::DOUBLE PRECISION AS avg_shellbrain_direct_tokens,
  AVG(shellbrain_explicit_tokens)::DOUBLE PRECISION AS avg_shellbrain_explicit_tokens,
  AVG(shellbrain_implicit_tokens)::DOUBLE PRECISION AS avg_shellbrain_implicit_tokens,
  AVG(read_count)::DOUBLE PRECISION AS avg_read_count,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY read_count)::DOUBLE PRECISION AS median_read_count
FROM problem_windows
GROUP BY repo_id, solve_window, read_cohort;
"""


USAGE_TOKEN_CAPTURE_HEALTH_SQL = """
CREATE OR REPLACE VIEW usage_token_capture_health AS
WITH synced_sessions AS (
  SELECT DISTINCT
    repo_id,
    host_app,
    host_session_key
  FROM episode_sync_runs
  WHERE episode_id IS NOT NULL
),
usage_sessions AS (
  SELECT
    repo_id,
    host_app,
    host_session_key,
    uses_exact_rows,
    uses_estimated_rows,
    has_nonzero_exact_rows,
    has_cursor_zero_rows
  FROM usage_session_tokens
)
SELECT
  ss.repo_id,
  ss.host_app,
  COUNT(*)::INTEGER AS synced_session_count,
  COUNT(*) FILTER (WHERE us.host_session_key IS NOT NULL)::INTEGER AS sessions_with_any_token_data,
  COUNT(*) FILTER (WHERE COALESCE(us.uses_exact_rows, FALSE))::INTEGER AS sessions_with_exact_data,
  COUNT(*) FILTER (
    WHERE NOT COALESCE(us.uses_exact_rows, FALSE)
      AND COALESCE(us.uses_estimated_rows, FALSE)
  )::INTEGER AS sessions_with_estimated_only_data,
  COUNT(*) FILTER (
    WHERE us.host_app = 'cursor'
      AND COALESCE(us.has_cursor_zero_rows, FALSE)
      AND NOT COALESCE(us.has_nonzero_exact_rows, FALSE)
  )::INTEGER AS cursor_zero_only_sessions,
  COUNT(*) FILTER (WHERE us.host_session_key IS NULL)::INTEGER AS sessions_without_token_data
FROM synced_sessions ss
LEFT JOIN usage_sessions us
  ON us.repo_id = ss.repo_id
 AND us.host_app = ss.host_app
 AND us.host_session_key = ss.host_session_key
GROUP BY ss.repo_id, ss.host_app;
"""
